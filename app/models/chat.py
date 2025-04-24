from typing import TypedDict, Literal, Dict, Any, Optional, Union
from dataclasses import dataclass
from asyncpg import Connection
from httpx import AsyncClient

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    UserPromptPart,
    TextPart,
)
from pydantic_ai.exceptions import UnexpectedModelBehavior


@dataclass
class Deps:
    client: AsyncClient
    db_connection: Connection


class ChatMessage(TypedDict):
    """Format of messages sent to the browser."""

    role: Literal['user', 'model', 'metadata']
    timestamp: str
    content: Union[str, Dict]
    conversation_id: str


def to_chat_message(m: ModelMessage, conversationId) -> ChatMessage:
    first_part = m.parts[0]
    if isinstance(m, ModelRequest):
        if isinstance(first_part, UserPromptPart):
            return {
                'role': 'user',
                "conversation_id": conversationId,
                'timestamp': first_part.timestamp.isoformat(),
                'content': first_part.content,
            }
    elif isinstance(m, ModelResponse):
        if isinstance(first_part, TextPart):
            return {
                'role': 'model',
                "conversation_id": conversationId,
                'timestamp': m.timestamp.isoformat(),
                'content': first_part.content,
            }
    raise UnexpectedModelBehavior(f'Unexpected message type for chat app: {m}')