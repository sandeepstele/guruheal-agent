from __future__ import annotations as _annotations

import asyncio
import json
import sqlite3
from collections.abc import AsyncIterator
from concurrent.futures.thread import ThreadPoolExecutor
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import partial
from pathlib import Path
from typing import Annotated, Any, Callable, Literal, TypeVar

import fastapi
import logfire
from fastapi import Depends, Request
from fastapi.responses import FileResponse, Response, StreamingResponse
from typing_extensions import LiteralString, ParamSpec, TypedDict

from pydantic_ai import Agent
from pydantic_ai.exceptions import UnexpectedModelBehavior
from pydantic_ai.messages import (
    ModelMessage,
    ModelMessagesTypeAdapter,
    ModelRequest,
    ModelResponse,
    TextPart,
    UserPromptPart,
)
from openai import AsyncOpenAI
from pydantic_ai.models.openai import OpenAIModel
import os
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo.errors import ConnectionFailure, OperationFailure, ServerSelectionTimeoutError

# Load environment variables
load_dotenv()

# Add MongoDB configuration
MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME")

# 'if-token-present' means nothing will be sent (and the example will work) if you don't have logfire configured
logfire.configure(send_to_logfire='if-token-present')

client = AsyncOpenAI(
    base_url='https://api.dosashop1.com/openai/v1',
    api_key=os.getenv('API_KEY'),
    default_headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {os.getenv('API_KEY')}",
        "api-key": os.getenv('API_KEY')
    }
)

model = OpenAIModel('gpt-4o', openai_client=client)

agent = Agent(model)

THIS_DIR = Path(__file__).parent


@asynccontextmanager
async def lifespan(_app: fastapi.FastAPI):
    async with MongoDatabase.connect(MONGO_URI, MONGO_DB_NAME) as db:
        yield {'db': db}


app = fastapi.FastAPI(lifespan=lifespan)
logfire.instrument_fastapi(app)


@app.get('/')
async def index() -> FileResponse:
    return FileResponse((THIS_DIR / 'chat_app.html'), media_type='text/html')


@app.get('/chat_app.ts')
async def main_ts() -> FileResponse:
    """Get the raw typescript code, it's compiled in the browser, forgive me."""
    return FileResponse((THIS_DIR / 'chat_app.ts'), media_type='text/plain')


async def get_db(request: Request) -> MongoDatabase:
    return request.state.db


@app.get('/chat/')
async def get_chat(database: MongoDatabase = Depends(get_db)) -> Response:
    msgs = await database.get_messages()
    return Response(
        b'\n'.join(json.dumps(to_chat_message(m)).encode('utf-8') for m in msgs),
        media_type='text/plain',
    )


class ChatMessage(TypedDict):
    """Format of messages sent to the browser."""

    role: Literal['user', 'model']
    timestamp: str
    content: str


def to_chat_message(m: ModelMessage) -> ChatMessage:
    first_part = m.parts[0]
    if isinstance(m, ModelRequest):
        if isinstance(first_part, UserPromptPart):
            return {
                'role': 'user',
                'timestamp': first_part.timestamp.isoformat(),
                'content': first_part.content,
            }
    elif isinstance(m, ModelResponse):
        if isinstance(first_part, TextPart):
            return {
                'role': 'model',
                'timestamp': m.timestamp.isoformat(),
                'content': first_part.content,
            }
    raise UnexpectedModelBehavior(f'Unexpected message type for chat app: {m}')


@app.post('/chat/')
async def post_chat(
    prompt: Annotated[str, fastapi.Form()],
    database: MongoDatabase = Depends(get_db)
) -> StreamingResponse:
    async def stream_messages():
        """Streams new line delimited JSON `Message`s to the client."""
        # stream the user prompt so that can be displayed straight away
        yield (
            json.dumps(
                {
                    'role': 'user',
                    'timestamp': datetime.now(tz=timezone.utc).isoformat(),
                    'content': prompt,
                }
            ).encode('utf-8')
            + b'\n'
        )
        # get the chat history so far to pass as context to the agent
        messages = await database.get_messages()
        # run the agent with the user prompt and the chat history
        async with agent.run_stream(prompt, message_history=messages) as result:
            async for text in result.stream(debounce_by=0.01):
                # text here is a `str` and the frontend wants
                # JSON encoded ModelResponse, so we create one
                m = ModelResponse(parts=[TextPart(text)], timestamp=result.timestamp())
                yield json.dumps(to_chat_message(m)).encode('utf-8') + b'\n'

        # add new messages (e.g. the user prompt and the agent response in this case) to the database
        await database.add_messages(result.new_messages_json())

    return StreamingResponse(stream_messages(), media_type='text/plain')


P = ParamSpec('P')
R = TypeVar('R')


class DatabaseError(Exception):
    """Custom exception for database operations"""
    pass

@dataclass
class MongoDatabase:
    """MongoDB implementation for chat message storage"""
    
    client: AsyncIOMotorClient
    db: AsyncIOMotorDatabase
    collection_name: str = "chat_messages"

    @classmethod
    @asynccontextmanager
    async def connect(
        cls,
        mongo_uri: str = "mongodb://localhost:27017",
        db_name: str = "chat_app"
    ) -> AsyncIterator[MongoDatabase]:
        with logfire.span('connect to MongoDB'):
            try:
                client = AsyncIOMotorClient(mongo_uri)
                # Verify connection
                await client.admin.command('ping')
                
                db = client[db_name]
                slf = cls(client=client, db=db)
                
                # Ensure indexes for both timestamps
                await db[slf.collection_name].create_index("created_at")
                await db[slf.collection_name].create_index("updated_at")
                
                yield slf
            except (ConnectionFailure, ServerSelectionTimeoutError) as e:
                raise DatabaseError(f"Failed to connect to MongoDB: {str(e)}")
            finally:
                client.close()

    async def add_messages(self, messages: bytes) -> None:
        try:
            # Convert bytes to JSON
            new_messages_json = json.loads(messages)
            current_time = datetime.now(timezone.utc)
            
            # First, try to find an existing document
            existing_doc = await self.db[self.collection_name].find_one(
                {},
                sort=[("created_at", -1)]
            )
            
            if existing_doc:
                # If document exists, append to it
                await self.db[self.collection_name].update_one(
                    {"_id": existing_doc["_id"]},
                    {
                        "$push": {
                            "message_list": {
                                "$each": new_messages_json
                            }
                        },
                        "$set": {
                            "updated_at": current_time
                        }
                    }
                )
            else:
                # If no document exists, create new one
                await self.db[self.collection_name].insert_one({
                    "message_list": new_messages_json,
                    "created_at": current_time,
                    "updated_at": current_time
                })
            
        except (OperationFailure, Exception) as e:
            raise DatabaseError(f"Failed to add messages: {str(e)}")

    async def get_messages(self) -> list[ModelMessage]:
        try:
            cursor = self.db[self.collection_name].find(
                {},
                sort=[("created_at", 1)]  # 1 for ascending order
            )
            
            messages: list[ModelMessage] = []
            async for doc in cursor:
                messages.extend(ModelMessagesTypeAdapter.validate_json(
                    json.dumps(doc["message_list"])
                ))
            return messages
            
        except (OperationFailure, Exception) as e:
            raise DatabaseError(f"Failed to retrieve messages: {str(e)}")


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(
        'chat_app:app', reload=True, reload_dirs=[str(THIS_DIR)]
    )