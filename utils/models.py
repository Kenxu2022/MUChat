from pydantic import BaseModel
from typing import List, Union, Any

class Usage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    streaming_time: float

class ChatMessage(BaseModel):
    role: str
    content: Union[str, List[Any]]

class Choices(BaseModel):
    message: ChatMessage

class UsageChunk(BaseModel):
    id: str
    object: str = "chat.completion.chunk"
    choices: List[Any] = []
    created: int
    model: str
    usage: Usage

class ChatCompletionChunk(UsageChunk):
    object: str = "chat.completion"
    choices: List[Choices]
    usage: Union[Usage, None] = None

class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[ChatMessage]
    stream: bool = False
