from typing import Optional, List, Tuple
import logfire
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIModel
from httpx import AsyncClient

# Import from root level core directory
from app.models.chat import Deps
from core.ai import get_llm_model
from .prompts.chat_prompt import get_system_prompt
from .tools.schema import WebSearchRequest, KnowledgeBaseRequest
from .tools.web_search import web_search as perform_web_search
from .tools.knowledge_base import query_knowledge_base as perform_knowledge_base_query

# Initialize OpenAI components
model = get_llm_model()

# Create and export the agent
chat_agent = Agent(
    model,
    system_prompt=get_system_prompt(),
    deps_type=Deps,
)

@chat_agent.tool
async def knowledge_base_search(ctx: RunContext[Deps], request: KnowledgeBaseRequest) -> dict:
    """
    Query the knowledge base for information about alternative medicine.
    
    Parameters:
        request: The search request with structure:
            {
                "query": str,  # The search query to find information
                "domain": str  # The domain to search within (e.g., "ayurveda")
            }
    
    Examples:
        {
            "query": "What are the basic principles of Ayurveda?",
            "domain": "ayurveda"
        }
        
        {
            "query": "Herbs used for treating diabetes",
            "domain": "ayurveda"
        }
    
    Returns:
        The search results from the knowledge base.
        
        On error:
        {
            "error": str,
            "message": str
        }
    """
    return await perform_knowledge_base_query(ctx, request)

@chat_agent.tool
async def web_search(ctx: RunContext[Deps], request: WebSearchRequest) -> dict:
    """
    Search the web for relevant information about alternative medicine and health topics.
    
    Parameters:
        request: The search request with structure:
            {
                "query": str  # The search query to find information
            }
    
    Examples:
        {
            "query": "What are the benefits of turmeric in Ayurvedic medicine"
        }
        
        {
            "query": "How does Siddha medicine treat respiratory issues"
        }
    
    Returns:
        The search results from the web search service.
        
        On error:
        {
            "error": str,
            "message": str
        }
    """
    return await perform_web_search(ctx, request)
