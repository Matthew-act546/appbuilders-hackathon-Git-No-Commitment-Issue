from pydantic import BaseModel, Field, field_validator


class AIStatus(BaseModel):
    available: bool
    server_available: bool
    model_available: bool
    model: str
    message: str


class GenerateRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=8000)

    @field_validator("prompt")
    @classmethod
    def trim_prompt(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Prompt must not be blank.")
        return value


class GenerateResponse(BaseModel):
    model: str
    response: str
