from pydantic import BaseModel, Field


class AIRequest(BaseModel):
    system_prompt: str
    user_prompt: str
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    model: str | None = None

class AIResponse(BaseModel):
    content: str
    model_used: str
    provider: str
