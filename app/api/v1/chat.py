from __future__ import annotations as _annotations

import json
import datetime
from pathlib import Path
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import FileResponse, Response, StreamingResponse
from httpx import AsyncClient
from app.models.chat import Deps
from app.models.chat import to_chat_message
from app.services.agents.chat_agent import chat_agent as agent
from pydantic_ai.messages import ModelResponse, TextPart
from app.utils.pg_utils import PgDatabase
from app.utils.pg_utils import DatabaseError
from app.services.agents.metadata_agent import metadata_agent
from app.services.agents.title_agent import title_agent
from core.middleware import correlation_id_ctx_var
from app.utils.redis_utils import retrieve_web_search_sources

router = APIRouter()

# Point to project root where the files are located
THIS_DIR = Path(__file__).parent.parent.parent.parent


async def get_db(request: Request) -> PgDatabase:
    return request.state.db

@router.get('/{conversation_id}')
async def get_chat(conversation_id: str, database: PgDatabase = Depends(get_db)) -> Response:
    # Get chronologically ordered messages with metadata interleaved
    messages_with_metadata = await database.get_chat_messages(conversation_id)

    return Response(
        json.dumps(messages_with_metadata).encode('utf-8'),
        media_type='application/json',
    )

@router.delete('/{conversation_id}')
async def delete_chat(conversation_id: str, database: PgDatabase = Depends(get_db)) -> Response:
    """Delete a conversation and all its associated messages."""
    try:
        await database.delete_conversation(conversation_id)
        return Response(
            json.dumps({"status": "success", "message": f"Conversation {conversation_id} deleted successfully"}).encode('utf-8'),
            media_type='application/json',
        )
    except DatabaseError as e:
        return Response(
            json.dumps({"status": "error", "message": str(e)}).encode('utf-8'),
            status_code=404 if "not found" in str(e) else 500,
            media_type='application/json',
        )

@router.post('/')
async def post_chat(
    prompt: Annotated[str, Form()],
    conversation_id: Annotated[str, Form()],
    language: Annotated[Optional[str], Form()] = None,
    use_web_search: Annotated[Optional[bool], Form()] = False,
    database: PgDatabase = Depends(get_db)
) -> StreamingResponse:
    async def stream_messages():
        """Streams new line delimited JSON `Message`s to the client."""
        # stream the user prompt so that can be displayed straight away
        print(f"Use web search: {use_web_search}")

        yield (
            json.dumps(
                {
                    'role': 'user',
                    "conversation_id": conversation_id,
                    'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    'content': prompt,
                }
            ).encode('utf-8')
            + b'\n'
        )
        
        messages = await database.get_messages(conversation_id)
        
        async with AsyncClient(timeout=30.0) as client, database._get_connection() as db_connection:
            deps = Deps(
                client=client,
                db_connection=db_connection,  # Use a connection from the pool
                language=language,  # Pass the language parameter to deps
                use_web_search=use_web_search  # Pass the use_web_search parameter to deps
            )
            
            async with agent.run_stream(prompt, deps=deps, message_history=messages) as result:
                async for text in result.stream(debounce_by=0.01):
                    m = ModelResponse(parts=[TextPart(text)], timestamp=result.timestamp())
                    yield json.dumps(to_chat_message(m, conversation_id)).encode('utf-8') + b'\n'
            
            search_data = None
            # Try to retrieve sources from Redis using correlation ID
            correlation_id = correlation_id_ctx_var.get()
            if correlation_id:
                web_search_sources = await retrieve_web_search_sources(correlation_id)
                if web_search_sources:
                    # Add sources to search data
                    if not search_data:
                        search_data = {}
                    search_data["sources"] = web_search_sources
            
            try:
                metadata_response = await metadata_agent.run(result.new_messages_json().decode('utf-8'), deps=deps)
                if not search_data:
                    search_data = {}
                search_data['follow_up_questions'] = metadata_response.data.questions
                search_data['provide_appointment_booking'] = metadata_response.data.provide_appointment_booking
                search_data['recommend_product'] = metadata_response.data.recommend_product
            except Exception as e:
                print(f"Error: {e}")
                if not search_data:
                    search_data = {}
                search_data['follow_up_questions'] = []
                search_data['provide_appointment_booking'] = False
                search_data['recommend_product'] = False

            yield (
                json.dumps(
                    {
                        'role': 'metadata',
                        "conversation_id": conversation_id,
                        'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                        'content': search_data
                    }
                ).encode('utf-8')
                + b'\n'
            )

            if len(messages) < 3:
                try:
                    title_response = await title_agent.run(result.all_messages_json().decode('utf-8'), deps=deps)
                    if title_response and title_response.data.title:
                        # Update the conversation title in the database
                        await database.update_conversation_title(conversation_id, title_response.data.title)
                except Exception as e:
                    print(f"Error generating title: {str(e)}")

            await database.add_messages(result.new_messages_json(), conversation_id, search_data)
            
    return StreamingResponse(stream_messages(), media_type='text/plain')

@router.get('/{user_id}/conversation_ids')
async def get_conversation_ids(user_id: str, database: PgDatabase = Depends(get_db)) -> Response:
    conversations = await database.get_conversation_ids(user_id)
    # If a conversation has no title, generate a placeholder
    for conversation in conversations:
        if not conversation.get("title"):
            conversation["title"] = f"Conversation {conversation['id'][:5]}"
    
    return Response(
        json.dumps(conversations).encode('utf-8'),
        media_type='application/json',
    )
    

@router.get('/ui/app.html')
async def index() -> FileResponse:
    return FileResponse(THIS_DIR / 'chat_app.html', media_type='text/html')

@router.get('/ui/app.ts')
async def main_ts() -> FileResponse:
    """Get the raw typescript code, it's compiled in the browser, forgive me."""
    return FileResponse(THIS_DIR / 'chat_app.ts', media_type='text/plain')

@router.post('/conversation')
async def create_conversation(
    user_id: str,
    database: PgDatabase = Depends(get_db)
) -> Response:
    """Create a new conversation for a user."""
    try:
        conversation_id = await database.create_conversation(user_id)
        return Response(
            conversation_id.encode('utf-8'),
            media_type='text/plain',
        )
    except DatabaseError as e:
        return Response(
            str(e).encode('utf-8'),
            status_code=400,
            media_type='text/plain',
        )