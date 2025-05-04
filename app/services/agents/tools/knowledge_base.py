import logfire
from typing import Dict
from pydantic_ai import RunContext
from app.models.chat import Deps
from .schema import KnowledgeBaseRequest
import os
import traceback
from httpx import ConnectError, ReadTimeout, HTTPStatusError

KNOWLEDGE_BASE_URL = os.getenv("RAG_URL")

# Domain to ID mapping
DOMAIN_TO_ID_MAP = {
    "ayurveda": ["doc-26a92f8bc882e5cee7b30c15a6827d3e"]
    # More domains can be added later
}

async def query_knowledge_base(ctx: RunContext[Deps], request: KnowledgeBaseRequest) -> Dict:
    """
    Query the knowledge base with domain-specific filtering.
    
    Args:
        ctx: Run context with dependencies
        request: Search parameters with query string and domain
        
    Returns:
        Success response: JSON response from knowledge base service
        Error response: {
            "error": "domain_not_found" | "query_failed" | "query_error",
            "message": str
        }
    """
    with logfire.span('Knowledge Base Query', params=request.model_dump()) as span:
        try:
            # Get IDs for the specified domain
            domain = request.domain.lower()
            ids = DOMAIN_TO_ID_MAP.get(domain, [])
            
            # If domain not found, return error
            if not ids:
                return {
                    "error": "domain_not_found",
                    "message": f"The domain '{domain}' is not supported. Available domains: {list(DOMAIN_TO_ID_MAP.keys())}"
                }
            
            query_body = {
                "query": request.query,
                "mode": "mix",
                "ids": ids,
                "top_k": 10
            }
            
            # Check if RAG_URL is set
            if not KNOWLEDGE_BASE_URL:
                span.set_status('error', "RAG_URL environment variable is not set")
                logfire.error("RAG_URL environment variable is not set", 
                    environment_vars=list(os.environ.keys()),
                    query=request.query,
                    domain=domain
                )
                return {
                    "error": "config_error",
                    "message": "Knowledge base URL (RAG_URL) is not configured"
                }
            
            logfire.info("Making knowledge base request", 
                query=request.query,
                domain=domain,
                ids=ids,
                url=KNOWLEDGE_BASE_URL
            )
            
            try:
                response = await ctx.deps.client.post(
                    KNOWLEDGE_BASE_URL,
                    json=query_body,
                    timeout=30.0  # Add explicit timeout
                )
                
                logfire.info("Received knowledge base response",
                    status_code=response.status_code,
                    response_headers=dict(response.headers),
                    response_size=len(response.content)
                )
                
                if response.status_code == 200:
                    response_json = response.json()
                    logfire.info("Parsed knowledge base response",
                        response_keys=list(response_json.keys())
                    )
                    
                    return response_json
                else:
                    error_detail = ""
                    try:
                        error_detail = response.json()
                    except:
                        error_detail = response.text[:200]  # First 200 chars of response
                        
                    span.set_status('error', f"Query failed with status {response.status_code}")
                    logfire.error("Knowledge base request failed",
                        status_code=response.status_code,
                        error_detail=error_detail,
                        response_headers=dict(response.headers)
                    )
                    return {
                        "error": "query_failed",
                        "message": f"Knowledge base query failed with status code: {response.status_code}. Details: {error_detail}"
                    }
            
            except ConnectError as ce:
                span.set_status('error', str(ce))
                logfire.error("Knowledge base connection error",
                    error=str(ce),
                    error_type="ConnectError",
                    traceback=traceback.format_exc(),
                    url=KNOWLEDGE_BASE_URL,
                    error_details="Unable to connect to the knowledge base server. Check if the service is running and accessible."
                )
                return {
                    "error": "connection_error",
                    "message": f"Failed to connect to knowledge base at {KNOWLEDGE_BASE_URL}: {str(ce)}"
                }
                
            except ReadTimeout as rt:
                span.set_status('error', str(rt))
                logfire.error("Knowledge base request timeout",
                    error=str(rt),
                    error_type="ReadTimeout",
                    timeout=30.0,
                    url=KNOWLEDGE_BASE_URL
                )
                return {
                    "error": "timeout_error",
                    "message": f"Knowledge base request timed out after 30 seconds: {str(rt)}"
                }
                
            except HTTPStatusError as hse:
                span.set_status('error', str(hse))
                logfire.error("Knowledge base HTTP status error",
                    error=str(hse),
                    error_type="HTTPStatusError",
                    status_code=hse.response.status_code if hasattr(hse, 'response') else 'unknown',
                    url=KNOWLEDGE_BASE_URL,
                    response_text=hse.response.text[:500] if hasattr(hse, 'response') else 'unknown'
                )
                return {
                    "error": "http_status_error",
                    "message": f"Knowledge base server returned an error status: {str(hse)}"
                }
                
            except Exception as he:
                span.set_status('error', str(he))
                logfire.error("HTTP error during knowledge base query",
                    error=str(he),
                    error_type=type(he).__name__,
                    traceback=traceback.format_exc(),
                    url=KNOWLEDGE_BASE_URL
                )
                return {
                    "error": "http_error",
                    "message": f"HTTP error during knowledge base query: {str(he)}"
                }
                
        except Exception as e:
            span.set_status('error', str(e))
            logfire.error("Knowledge base query failed", 
                error=str(e),
                error_type=type(e).__name__,
                error_traceback=traceback.format_exc(),
                params=request.model_dump()
            )
            return {
                "error": "query_error",
                "message": f"Failed to perform knowledge base query: {str(e)}"
            } 