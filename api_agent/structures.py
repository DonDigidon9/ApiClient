from pydantic import BaseModel
from typing import List, Optional

class LLM(BaseModel):
    base_url: str
    api_key: str
    model: str

class MCP(BaseModel):
    url: str
    token: str
    name: str

class Message(BaseModel):
    text: str

class Author(BaseModel):
    name: str

class LLMConfig(BaseModel):
    id: int

class OpenAIMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    model: str # Это поле для OpenAI-совместимости
    messages: List[OpenAIMessage] # Это поле для OpenAI-совместимости
    stream: Optional[bool] = False
    chat_id: int

class UserRequest(BaseModel):
    content: str
    stream: Optional[bool] = False
