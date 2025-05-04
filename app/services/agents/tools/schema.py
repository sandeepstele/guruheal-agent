from pydantic import BaseModel, Field
from typing import List

class KnowledgeBaseRequest(BaseModel):
    """
    Request parameters for querying the knowledge base with domain-specific context.
    """
    query: str = Field(
        ...,
        description="The search query to find relevant information from the knowledge base"
    )
    domain: str = Field(
        ...,
        description="The domain to search within (e.g., 'ayurveda', 'homeopathy', 'siddha')",
    )
    
    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "query": "What are the basic principles of Ayurveda?",
                    "domain": "ayurveda"
                },
                {
                    "query": "Herbs used for treating diabetes",
                    "domain": "ayurveda"
                }
            ]
        }

class WebSearchRequest(BaseModel):
    query: str = Field(
        ...,
        description="The search query to find relevant information"
    )

class MetadataResponse(BaseModel):
    """Response with follow-up questions, appointment booking flag, and product recommendation flag"""
    questions: List[str] = Field(
        description="List of follow-up questions the user might want to ask next",
        max_items=4
    )
    provide_appointment_booking: bool = Field(
        description="Flag indicating whether an appointment booking link should be provided",
        default=False
    )
    recommend_product: bool = Field(
        description="Flag indicating whether product recommendations should be shown",
        default=False
    )

class TitleResponse(BaseModel):
    """Response with a generated title for the conversation"""
    title: str = Field(
        description="A short, descriptive title for the conversation (1-3 words)",
        max_length=50
    )