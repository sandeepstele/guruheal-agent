<think>Let me create comprehensive documentation that outlines the implementation of this feature. The documentation will include:

1. The problem statement
2. The proposed solution
3. Implementation steps
4. Code structure
5. Redis utility module design
6. Integration points

I'll write this in Markdown format as requested.</think># Web Search Sources Implementation Documentation

## Overview

This document outlines the implementation strategy for separating web search result sources from the main agent response, enabling us to:

1. Return only essential information to the agent (reducing token usage)
2. Still provide source attribution to end users
3. Maintain system performance and scalability

## Problem Statement

When performing web searches, the response contains both the informational message and source attributions. Sending the entire response to the LLM agent is inefficient because:

- Sources consume token budget unnecessarily
- The agent typically doesn't need source information to formulate responses
- This increases costs and potentially reduces performance

However, source attribution is valuable for end users to evaluate information credibility.

## Solution Architecture

We will implement a Redis-based approach to temporarily store source information while only sending the message content to the agent. The overall flow will be:

1. Web search tool executes search and gets full response (message + sources)
2. Tool stores sources in Redis with correlation ID as key
3. Tool returns only message content to agent
4. Agent processes message normally
5. Before final storage, API retrieves sources from Redis
6. Complete data (message + sources) is sent to client and stored in database

## Implementation Steps

### 1. Create Redis Utilities Module

Create a new file `app/utils/redis_utils.py` to handle Redis operations:

```python
import json
import asyncio
from typing import Any, Dict, Optional
import redis.asyncio as redis
from core.config import settings  # Assuming config exists

# Redis client instance
_redis_client = None

async def get_redis_client() -> redis.Redis:
    """Get or initialize the Redis client."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            password=settings.REDIS_PASSWORD,
            decode_responses=True
        )
    return _redis_client

async def store_web_search_sources(correlation_id: str, sources: Any, ttl: int = 900) -> bool:
    """
    Store web search sources in Redis with the correlation ID as key.
    
    Args:
        correlation_id: The request correlation ID
        sources: The sources data to store
        ttl: Time-to-live in seconds (default: 15 minutes)
        
    Returns:
        bool: Success status
    """
    try:
        client = await get_redis_client()
        key = f"web_search:{correlation_id}"
        
        # Serialize sources to JSON
        value = json.dumps(sources)
        
        # Store in Redis with TTL
        await client.set(key, value, ex=ttl)
        return True
    except Exception as e:
        # Log the error
        print(f"Redis store error: {str(e)}")
        return False

async def retrieve_web_search_sources(correlation_id: str) -> Optional[Dict]:
    """
    Retrieve web search sources from Redis.
    
    Args:
        correlation_id: The request correlation ID
        
    Returns:
        Optional[Dict]: The sources data or None if not found
    """
    try:
        client = await get_redis_client()
        key = f"web_search:{correlation_id}"
        
        # Get value from Redis
        value = await client.get(key)
        if value:
            # Parse JSON string back to dict
            return json.loads(value)
        return None
    except Exception as e:
        # Log the error
        print(f"Redis retrieve error: {str(e)}")
        return None

async def delete_web_search_sources(correlation_id: str) -> bool:
    """
    Delete web search sources from Redis after they've been used.
    
    Args:
        correlation_id: The request correlation ID
        
    Returns:
        bool: Success status
    """
    try:
        client = await get_redis_client()
        key = f"web_search:{correlation_id}"
        await client.delete(key)
        return True
    except Exception as e:
        # Log the error
        print(f"Redis delete error: {str(e)}")
        return False
```

### 2. Modify Web Search Tool

Update `app/services/agents/chat_agent/tools/web_search.py` to store sources in Redis:

```python
from typing import Dict
import logfire
from pydantic_ai import RunContext
from httpx import AsyncClient, HTTPError
from app.models.chat import Deps
from .schema import WebSearchRequest
from core.context_var import correlation_id_ctx_var
from app.utils.redis_utils import store_web_search_sources

async def web_search(ctx: RunContext[Deps], request: WebSearchRequest) -> Dict:
    """
    Search the web for relevant information using a specialized search service.
    
    Args:
        ctx: The context containing the HTTP client
        request: Search parameters with query string
        
    Returns:
        Success response: JSON response from search service
        Error response: {
            "error": "search_failed" | "search_error",
            "message": str
        }
    """
    with logfire.span('Web Search', params=request.model_dump()) as span:
        try:
            # ... existing search code ...
            
            # When processing response:
            if response.status_code == 200:
                response_json = response.json()
                logfire.info("Parsed web search response",
                    response_keys=list(response_json.keys())
                )
                
                # Extract message and sources
                message = response_json.get("message", "")
                sources = response_json.get("sources", [])
                
                # Store sources in Redis using correlation ID
                correlation_id = correlation_id_ctx_var.get()
                if sources and correlation_id:
                    await store_web_search_sources(correlation_id, sources)
                    logfire.info("Stored web search sources in Redis", 
                        correlation_id=correlation_id,
                        sources_count=len(sources)
                    )
                
                # Return only the message part to agent
                return {"message": message}
                
            # ... remainder of existing error handling ...
```

### 3. Update Chat API Endpoint

Modify `app/api/v1/chat.py` to retrieve sources before saving to database:

```python
# ... existing imports ...
from core.context_var import correlation_id_ctx_var
from app.utils.redis_utils import retrieve_web_search_sources, delete_web_search_sources

# ... existing endpoint code ...

@router.post('/')
async def post_chat(
    prompt: Annotated[str, Form()],
    conversation_id: Annotated[str, Form()],
    database: PgDatabase = Depends(get_db)
) -> StreamingResponse:
    async def stream_messages():
        # ... existing code ...
        
        async with agent.run_stream(prompt, deps=deps, message_history=messages) as result:
            async for text in result.stream(debounce_by=0.01):
                m = ModelResponse(parts=[TextPart(text)], timestamp=result.timestamp())
                yield json.dumps(to_chat_message(m, conversation_id)).encode('utf-8') + b'\n'

        # Get search data from the messages
        search_data = extract_search_data(result.new_messages())
        
        # Try to retrieve sources from Redis using correlation ID
        correlation_id = correlation_id_ctx_var.get()
        if correlation_id:
            web_search_sources = await retrieve_web_search_sources(correlation_id)
            if web_search_sources:
                # Add sources to search data
                if "web_search" in search_data:
                    search_data["web_search"]["sources"] = web_search_sources
                else:
                    search_data["web_search"] = {"sources": web_search_sources}
                
                # Clean up Redis (optional)
                await delete_web_search_sources(correlation_id)
        
        yield (
            json.dumps(
                {
                    'role': 'metadata',
                    "conversation_id": conversation_id,
                    'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    'content': search_data,
                }
            ).encode('utf-8')
            + b'\n'
        )
        
        yield json.dumps(search_data).encode('utf-8')
        
        # Add messages to database with search data if present
        await database.add_messages(result.new_messages_json(), conversation_id, search_data)
    
    return StreamingResponse(stream_messages(), media_type='text/plain')
```

## Configuration Updates

Add Redis configuration settings to your environment variables or config file:

```python
# In core/config.py or similar
class Settings:
    # ... existing settings ...
    
    # Redis settings
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))
    REDIS_PASSWORD: str = os.getenv("REDIS_PASSWORD", "")
    REDIS_TTL_SECONDS: int = int(os.getenv("REDIS_TTL_SECONDS", "900"))  # 15 minutes default
```

## Deployment Considerations

### Redis Deployment

For production environments:
- Consider using Redis with persistence enabled
- Set up Redis in a clustered mode for high availability
- Use Redis SSL for secure communication

### Error Handling

The implementation includes basic error handling, but consider enhancing it:
- Add more detailed logging
- Implement retry mechanisms for transient Redis errors
- Add monitoring for Redis performance and errors

### Security Considerations

- Use Redis AUTH for authentication
- Consider network isolation for Redis instances
- Avoid storing sensitive data in Redis (the sources should be non-sensitive)
- Set reasonable TTLs to avoid data leakage

## Performance Considerations

Redis operations are generally fast, but be mindful of:
- Large source data sets (consider compression if sources are large)
- Redis connection pool sizing
- Monitoring Redis memory usage

## Testing Strategy

1. **Unit Tests**: 
   - Test Redis utility functions with mocked Redis client
   - Test correlation ID access in isolated environments

2. **Integration Tests**:
   - Test the full flow from web search to client response
   - Verify sources are correctly stored and retrieved
   - Test error cases (Redis unavailable, etc.)

3. **Manual Testing**:
   - Verify sources are displayed correctly in the UI
   - Check performance impact with various search results

## Conclusion

This implementation provides an efficient way to separate agent messages from source information, reducing token usage while still providing valuable sources to end users. By using Redis as a temporary storage mechanism, we maintain performance while keeping the system loosely coupled.
