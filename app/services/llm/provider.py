from typing import Protocol
from app.services.llm.models import AIRequest, AIResponse


class AIProvider(Protocol):
    """
    Standard interface for all LLM providers (xAI, OpenAI, Gemini, etc.).
    Any concrete provider class must implement the methods defined here.
    """
    
    async def generate(self, request: AIRequest) -> AIResponse:
        """
        Send a prompt to the LLM provider and return a standardized response.
        
        Args:
            request (AIRequest): The standardized request containing prompts and config.
            
        Returns:
            AIResponse: The standardized response containing the generated content.
        """
        ...
