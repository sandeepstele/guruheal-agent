import logfire
from typing import Dict
from pydantic_ai import RunContext
from app.models.chat import Deps
from .schema import KnowledgeBaseRequest

KNOWLEDGE_BASE_URL = "http://localhost:9621/query"

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
                    
            except Exception as he:
                span.set_status('error', str(he))
                logfire.error("HTTP error during knowledge base query",
                    error=str(he),
                    error_type=type(he).__name__
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
                error_traceback=logfire.format_exc(),
                params=request.model_dump()
            )
            return {
                "error": "query_error",
                "message": f"Failed to perform knowledge base query: {str(e)}"
            } 