from pydantic import BaseModel, Field


class OcrBox(BaseModel):
    text: str
    confidence: float
    box: list[list[float]]


class OcrPage(BaseModel):
    page: int
    text: str
    boxes: list[OcrBox]


class OcrResponse(BaseModel):
    filename: str
    page_count: int
    text: str
    pages: list[OcrPage]


class AiTextRequest(BaseModel):
    text: str = Field(min_length=1)


class ChatMessage(BaseModel):
    role: str
    content: str


class AskRequest(BaseModel):
    text: str = Field(min_length=1)
    question: str = Field(min_length=1)
    history: list[ChatMessage] = []
