import os
import httpx
from fastapi import HTTPException, status

from app.services.llm.models import AIRequest, AIResponse


class XAIProvider:
    API_URL = "https://api.x.ai/v1/chat/completions"
    PROVIDER_NAME = "xAI"

    def __init__(self):
        self.api_key = os.getenv("XAI_API_KEY")
        self.default_model = os.getenv("XAI_MODEL", "grok-4.3")

        if not self.api_key:
            raise ValueError("XAI_API_KEY environment variable is not set")

    async def generate(self, request: AIRequest) -> AIResponse:
        model_to_use = request.model or self.default_model

        payload = {
            "model": model_to_use,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt}
            ],
            "temperature": request.temperature
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                self.API_URL,
                json=payload,
                headers=headers
            )
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Upstream AI provider error: {response.text}"
                )
                
            data = response.json()
            
            return AIResponse(
                content=data["choices"][0]["message"]["content"],
                model_used=model_to_use,
                provider=self.PROVIDER_NAME
            )
