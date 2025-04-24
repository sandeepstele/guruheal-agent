from typing import Dict
import logfire
from pydantic_ai import RunContext
from httpx import AsyncClient, HTTPError
from app.models.chat import Deps
from .schema import WebSearchRequest
from core.middleware import correlation_id_ctx_var
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
            search_body = {
                "chatModel": {
                    "provider": "custom_openai",
                    "model": "meta-llama/llama-3.3-70b-instruct:free"
                },
                "embeddingModel": {
                    "provider": "openai",
                    "model": "text-embedding-3-large"
                },
                "optimizationMode": "speed",
                "focusMode": "webSearch",
                "query": request.query,
                "history": []
            }
            
            logfire.info("Making web search request", 
                query=request.query,
                url="http://searchengine.vesselmatch.com:3001/api/search"
            )
            
            async with AsyncClient() as client:
                try:
                    response = await client.post(
                        "http://searchengine.vesselmatch.com:3001/api/search",
                        json=search_body,
                        timeout=30.0  # Add explicit timeout
                    )
                    
                    logfire.info("Received web search response",
                        status_code=response.status_code,
                        response_headers=dict(response.headers),
                        response_size=len(response.content)
                    )
                    
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
                        elif not correlation_id:
                            logfire.warning("No correlation ID available, cannot store web search sources")
                        
                        # Return only the message part to agent
                        return {"message": message}
                    else:
                        error_detail = ""
                        try:
                            error_detail = response.json()
                        except:
                            error_detail = response.text[:200]  # First 200 chars of response
                            
                        span.set_status('error', f"Search failed with status {response.status_code}")
                        logfire.error("Web search request failed",
                            status_code=response.status_code,
                            error_detail=error_detail,
                            response_headers=dict(response.headers)
                        )
                        return {
                            "error": "search_failed",
                            "message": f"Web search failed with status code: {response.status_code}. Details: {error_detail}"
                        }
                        
                except HTTPError as he:
                    span.set_status('error', str(he))
                    logfire.error("HTTP error during web search",
                        error=str(he),
                        error_type=type(he).__name__
                    )
                    return {
                        "error": "http_error",
                        "message": f"HTTP error during web search: {str(he)}"
                    }
                    
        except Exception as e:
            span.set_status('error', str(e))
            logfire.error("Web search failed", 
                error=str(e),
                error_type=type(e).__name__,
                error_traceback=logfire.format_exc(),
                params=request.model_dump()
            )
            return {
                "error": "search_error",
                "message": f"Failed to perform web search: {str(e)}"
            }
