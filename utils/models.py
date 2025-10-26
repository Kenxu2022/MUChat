from pydantic import BaseModel
from typing import List

class Usage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    streaming_time: float

class ChatMessage(BaseModel):
    role: str
    content: str

class Choices(BaseModel):
    message: ChatMessage

class UsageChunk(BaseModel):
    id: str
    object: str = "chat.completion.chunk"
    created: int
    model: str
    usage: Usage

class ChatCompletionChunk(UsageChunk):
    object: str = "chat.completion"
    choices: List[Choices]
    usage: Usage

class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[ChatMessage]
    stream: bool = False
