import os
import httpx
from fastapi import HTTPException, status
from app.services.llm.models import AIRequest, AIResponse

class XAIProvider:
    API_URL = "https://api.x.ai/v1/responses"
    PROVIDER_NAME = "xAI"

    def __init__(self):
        self.api_key = os.getenv("XAI_API_KEY")
        self.default_model = os.getenv("XAI_MODEL", "grok-4.3")

        if not self.api_key:
            raise ValueError("XAI_API_KEY environment variable is not set")

    async def generate(self, request: AIRequest) -> AIResponse:
        model_to_use = request.model or self.default_model

        # Build content array
        user_content = [{"type": "input_text", "text": request.user_prompt}]

        if request.document_url:
            user_content.append({
                "type": "input_file",
                "file_url": request.document_url
            })

        payload = {
            "model": model_to_use,
            "input": [
                {
                    "role": "system",
                    "content": request.system_prompt
                },
                {
                    "role": "user",
                    "content": user_content
                }
            ],
            "temperature": request.temperature,
            "store": True
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                self.API_URL,
                json=payload,
                headers=headers
            )

            if response.status_code != 200:
                error_detail = response.text
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Upstream AI provider error: {error_detail}"
                )

            data = response.json()

            # Extract the final output text (Responses API format)
            try:
                # Get the last assistant message's text
                last_output = data["output"][-1]
                content_parts = last_output["content"]
                text_part = next((part["text"] for part in content_parts if part.get("type") == "output_text"), "")
                content = text_part
            except (KeyError, IndexError, StopIteration):
                content = data.get("output", [{}])[-1].get("content", "")

            return AIResponse(
                content=content,
                model_used=model_to_use,
                provider=self.PROVIDER_NAME
            )
