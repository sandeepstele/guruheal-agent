from __future__ import annotations as _annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Dict
from app.models.chat import to_chat_message
import os
import datetime

import logfire  

from pydantic_ai.messages import (
    ModelMessage,
    ModelMessagesTypeAdapter,
)

import asyncio
from typing import Any, AsyncIterator, List

import asyncpg
from asyncpg import Connection, Pool
from contextlib import asynccontextmanager
from logfire import span, instrument_asyncpg

class DatabaseError(Exception):
    """Custom exception for database operations"""
    pass

@dataclass
class PgDatabase:
    """Database to store chat messages in PostgreSQL."""

    pool: Pool
    _loop: asyncio.AbstractEventLoop

    @classmethod
    @asynccontextmanager
    async def connectToDb(
        cls,
        host: str = os.getenv('POSTGRES_HOST'),
        port: int = os.getenv('POSTGRES_PORT'),
        user: str = os.getenv('POSTGRES_USER'),
        password: str = os.getenv('POSTGRES_PASSWORD'),
        database: str = os.getenv('POSTGRES_DATABASE'),
        min_size: int = 2,
        max_size: int = 10
    ) -> AsyncIterator['PgDatabase']:
        with span('connect to DB'):
            loop = asyncio.get_event_loop()
            try:
                # Create a connection pool instead of a single connection
                pool = await asyncpg.create_pool(
                    host=host,
                    port=port,
                    user=user,
                    password=password,
                    database=database,
                    min_size=min_size,
                    max_size=max_size,
                    command_timeout=60.0,
                    timeout=30.0,
                )
                slf = cls(pool, loop)
                yield slf
            except Exception as e:
                raise DatabaseError(f"Failed to connect to PostgreSQL: {str(e)}")
            finally:
                if 'pool' in locals():
                    await pool.close()

    @asynccontextmanager
    async def _get_connection(self) -> AsyncIterator[Connection]:
        """Get a connection from the pool and release it when done."""
        con = await self.pool.acquire()
        try:
            yield con
        finally:
            await self.pool.release(con)

    async def add_messages(self, messages: bytes, conversation_id: str, search_data: Optional[Dict] = None):
        """Store raw messages without any filtering and update conversation's updated_at timestamp."""
        try:
            # Convert bytes to string and parse JSON
            messages_str = messages.decode('utf-8')
            messages_list = json.loads(messages_str)
            
            async with self._get_connection() as con:
                # Insert with search_data if present
                if search_data:
                    await con.execute(
                        'INSERT INTO messages (message_list, conversation_id, search_data) VALUES ($1, $2, $3);',
                        json.dumps(messages_list), conversation_id, json.dumps(search_data)
                    )
                else:
                    await con.execute(
                        'INSERT INTO messages (message_list, conversation_id) VALUES ($1, $2);',
                        json.dumps(messages_list), conversation_id
                    )
                
                # Update the conversation's updated_at timestamp
                await con.execute(
                    'UPDATE conversations SET updated_at = NOW() WHERE id = $1;',
                    conversation_id
                )
        except json.JSONDecodeError as e:
            raise DatabaseError(f"Invalid JSON format in messages: {str(e)}")
        except Exception as e:
            raise DatabaseError(f"Failed to add messages: {str(e)}")

    async def get_chat_messages(self, conversation_id: str) -> List[Dict]:
        """Get chat messages with metadata interleaved chronologically."""
        try:
            async with self._get_connection() as con:
                rows = await con.fetch(
                    'SELECT id, message_list, search_data, created_at FROM messages WHERE conversation_id = $1 ORDER BY created_at',
                    conversation_id
                )
            
            chronological_response = []
            
            for row in rows:
                # Parse the JSON string to dict
                message_list = json.loads(row['message_list'])
                search_data = json.loads(row['search_data']) if row['search_data'] else None
                
                processed_message_list = []
                for msg in message_list:
                    # Filter out tool calls and system prompts as before
                    if (isinstance(msg, dict) and 
                        "parts" in msg and 
                        msg["parts"] and 
                        isinstance(msg["parts"][0], dict) and
                        "tool_name" in msg["parts"][0]):
                        continue
                    
                    # For messages with system prompts, filter out only the system-prompt parts
                    if isinstance(msg, dict) and "parts" in msg:
                        filtered_msg = msg.copy()
                        filtered_msg["parts"] = [
                            part for part in msg["parts"]
                            if not (isinstance(part, dict) and part.get("part_kind") == "system-prompt")
                        ]
                        
                        # Only add if there are still parts left after filtering
                        if filtered_msg["parts"]:
                            processed_message_list.append(filtered_msg)
                    else:
                        # Message doesn't have parts to filter, include as is
                        processed_message_list.append(msg)
                
                # Only validate if we have messages after filtering
                if processed_message_list:
                    model_messages = ModelMessagesTypeAdapter.validate_json(
                        json.dumps(processed_message_list)
                    )
                    
                    # Convert to chat format
                    for m in model_messages:
                        chat_message = to_chat_message(m, conversation_id)
                        chronological_response.append(chat_message)
                    
                    # If this message has search_data, add metadata right after
                    if search_data:
                        metadata_message = {
                            'role': 'metadata',
                            'conversation_id': conversation_id,
                            'timestamp': row['created_at'].isoformat() if row['created_at'] else datetime.datetime.now(datetime.timezone.utc).isoformat(),
                            'content': search_data
                        }
                        chronological_response.append(metadata_message)
            
            return chronological_response
        except json.JSONDecodeError as e:
            raise DatabaseError(f"Invalid JSON format in stored messages: {str(e)}")
        except Exception as e:
            raise DatabaseError(f"Failed to retrieve chat messages: {str(e)}")
    
    async def get_messages(self, conversation_id: str, limit: int = 5) -> List[ModelMessage]:
        """
        Get the most recent message exchanges in chronological order.
        If total messages > limit, always includes the first message along with recent messages.
        """
        try:
            async with self._get_connection() as con:
                # First, get the total count of messages for this conversation
                total_count = await con.fetchval(
                    'SELECT COUNT(*) FROM messages WHERE conversation_id = $1',
                    conversation_id
                )

                if total_count <= limit:
                    # If total messages are within limit, fetch all messages
                    rows = await con.fetch(
                        'SELECT message_list FROM messages WHERE conversation_id = $1 ORDER BY created_at ASC',
                        conversation_id
                    )
                else:
                    # If total messages exceed limit, get first message and recent messages
                    rows = await con.fetch(
                        '''
                        WITH first_message AS (
                            SELECT message_list, created_at
                            FROM messages
                            WHERE conversation_id = $1
                            ORDER BY created_at ASC
                            LIMIT 1
                        ),
                        recent_messages AS (
                            SELECT message_list, created_at
                            FROM messages
                            WHERE conversation_id = $1
                            AND created_at > (
                                SELECT created_at FROM first_message
                            )
                            ORDER BY created_at DESC
                            LIMIT $2
                        )
                        SELECT message_list FROM (
                            SELECT * FROM first_message
                            UNION ALL
                            SELECT * FROM recent_messages
                        )
                        AS combined_messages
                        ORDER BY created_at ASC
                        ''',
                        conversation_id,
                        limit - 1  # Reduce limit by 1 to account for first message
                    )

            messages: List[ModelMessage] = []
            for row in rows:
                try:
                    message_list = json.loads(row['message_list'])
                    validated_messages = ModelMessagesTypeAdapter.validate_json(
                        json.dumps(message_list)
                    )
                    messages.extend(validated_messages)
                except Exception as e:
                    print(f"Error processing message: {str(e)}")
                    continue

            return messages

        except Exception as e:
            raise DatabaseError(f"Failed to retrieve messages: {str(e)}")

    async def get_conversation_ids(self, user_id: str) -> List[Dict]:
        try:
            async with self._get_connection() as con:
                rows = await con.fetch(
                    'SELECT id, title, updated_at FROM conversations WHERE user_id = $1 ORDER BY updated_at DESC', 
                    user_id
                )
            return [{"id": str(row['id']), 
                    "title": row['title'] if row['title'] else None, 
                    "last_used": row['updated_at'].isoformat() if row['updated_at'] else None} 
                    for row in rows]
        except Exception as e:
            raise DatabaseError(f"Failed to retrieve conversation IDs: {str(e)}")

    async def create_conversation(self, user_id: str) -> str:
        """
        Create a new conversation for a user and return the conversation ID.
        
        Args:
            user_id: The UUID of the user as string
            
        Returns:
            str: The UUID of the newly created conversation
            
        Raises:
            DatabaseError: If the database operation fails
        """
        try:
            async with self._get_connection() as con:
                row = await con.fetchrow(
                    'INSERT INTO conversations (user_id) VALUES ($1) RETURNING id',
                    user_id
                )
            return str(row['id'])  # Convert UUID to string
        except Exception as e:
            raise DatabaseError(f"Failed to create conversation: {str(e)}")

    async def delete_conversation(self, conversation_id: str) -> bool:
        """
        Delete a conversation and all its associated messages.
        
        Args:
            conversation_id: The UUID of the conversation to delete
            
        Returns:
            bool: True if the conversation was successfully deleted
            
        Raises:
            DatabaseError: If the database operation fails
        """
        try:
            async with self._get_connection() as con:
                # Messages will be automatically deleted due to CASCADE
                result = await con.execute(
                    'DELETE FROM conversations WHERE id = $1;',
                    conversation_id
                )
                
                # Check if any rows were affected
                if result == "DELETE 0":
                    raise DatabaseError(f"Conversation with ID {conversation_id} not found")
                    
                return True
        except Exception as e:
            if isinstance(e, DatabaseError):
                raise e
            raise DatabaseError(f"Failed to delete conversation: {str(e)}")

    async def update_conversation_title(self, conversation_id: str, title: str) -> bool:
        """
        Update the title of a conversation.
        
        Args:
            conversation_id: The UUID of the conversation
            title: The new title for the conversation
            
        Returns:
            bool: True if the title was successfully updated
            
        Raises:
            DatabaseError: If the database operation fails
        """
        try:
            async with self._get_connection() as con:
                result = await con.execute(
                    'UPDATE conversations SET title = $1 WHERE id = $2;',
                    title, conversation_id
                )
                
                # Check if any rows were affected
                if result == "UPDATE 0":
                    raise DatabaseError(f"Conversation with ID {conversation_id} not found")
                    
                return True
        except Exception as e:
            if isinstance(e, DatabaseError):
                raise e
            raise DatabaseError(f"Failed to update conversation title: {str(e)}")

    
