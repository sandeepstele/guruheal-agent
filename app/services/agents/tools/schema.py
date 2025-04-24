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

class FollowUpQuestionsResponse(BaseModel):
    """Response containing follow-up questions based on conversation history."""
    questions: List[str] = Field(
        ...,
        description="List of follow-up questions related to the conversation",
        max_items=4
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "questions": [
                    "What are the fundamental principles of Ayurveda regarding digestion?",
                    "How does Siddha medicine approach respiratory conditions?",
                    "Are there any herbal remedies traditionally used for joint pain?",
                    "How does Gurubalaa Healthcare integrate traditional and modern approaches?"
                ]
            }
        }