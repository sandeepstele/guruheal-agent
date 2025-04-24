import json
import asyncio
from typing import Any, Dict, Optional
import redis.asyncio as redis
import logging

logger = logging.getLogger(__name__)

# Redis connection details
REDIS_URL = "redis://default:654UlXnvIF4CDiwJHjT56DEu5gLzeeyc@redis-13009.c305.ap-south-1-1.ec2.redns.redis-cloud.com:13009"

# Redis client instance (singleton)
_redis_client = None

async def get_redis_client() -> redis.Redis:
    """Get or initialize the Redis client."""
    global _redis_client
    if _redis_client is None:
        try:
            _redis_client = redis.Redis.from_url(
                REDIS_URL,
                decode_responses=True
            )
            # Test connection
            await _redis_client.ping()
            logger.info("Redis connection established successfully")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {str(e)}")
            _redis_client = None
    return _redis_client

async def store_web_search_sources(correlation_id: str, sources: Any, ttl: int = 180) -> bool:
    """
    Store web search sources in Redis with the correlation ID as key.
    
    Args:
        correlation_id: The request correlation ID
        sources: The sources data to store
        ttl: Time-to-live in seconds (default: 15 minutes)
        
    Returns:
        bool: Success status
    """
    if not correlation_id:
        logger.error("Cannot store sources: No correlation ID provided")
        return False
        
    try:
        client = await get_redis_client()
        if not client:
            logger.error("Redis client unavailable for storing sources")
            return False
            
        key = f"web_search:{correlation_id}"
        
        # Serialize sources to JSON
        value = json.dumps(sources)
        
        # Store in Redis with TTL
        await client.set(key, value, ex=ttl)
        logger.info(f"Stored web search sources in Redis for correlation ID: {correlation_id}")
        return True
    except Exception as e:
        logger.error(f"Redis store error: {str(e)}")
        return False

async def retrieve_web_search_sources(correlation_id: str) -> Optional[Dict]:
    """
    Retrieve web search sources from Redis.
    
    Args:
        correlation_id: The request correlation ID
        
    Returns:
        Optional[Dict]: The sources data or None if not found
    """
    if not correlation_id:
        logger.error("Cannot retrieve sources: No correlation ID provided")
        return None
        
    try:
        client = await get_redis_client()
        if not client:
            logger.error("Redis client unavailable for retrieving sources")
            return None
            
        key = f"web_search:{correlation_id}"
        
        # Get value from Redis
        value = await client.get(key)
        if value:
            # Parse JSON string back to dict/list
            sources = json.loads(value)
            logger.info(f"Retrieved web search sources from Redis for correlation ID: {correlation_id}")
            return sources
        
        logger.warning(f"No sources found in Redis for correlation ID: {correlation_id}")
        return None
    except Exception as e:
        logger.error(f"Redis retrieve error: {str(e)}")
        return None

async def delete_web_search_sources(correlation_id: str) -> bool:
    """
    Delete web search sources from Redis after they've been used.
    
    Args:
        correlation_id: The request correlation ID
        
    Returns:
        bool: Success status
    """
    if not correlation_id:
        logger.error("Cannot delete sources: No correlation ID provided")
        return False
        
    try:
        client = await get_redis_client()
        if not client:
            logger.error("Redis client unavailable for deleting sources")
            return False
            
        key = f"web_search:{correlation_id}"
        
        # Delete the key
        result = await client.delete(key)
        if result:
            logger.info(f"Deleted web search sources from Redis for correlation ID: {correlation_id}")
            return True
        
        logger.warning(f"No sources found to delete for correlation ID: {correlation_id}")
        return False
    except Exception as e:
        logger.error(f"Redis delete error: {str(e)}")
        return False 