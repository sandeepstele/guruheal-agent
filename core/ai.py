from openai import AsyncOpenAI
from pydantic_ai.models.openai import OpenAIModel
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# def get_openai_client() -> AsyncOpenAI:
#     """Configure and return OpenAI client."""
#     return AsyncOpenAI(
#         base_url='https://openrouter.ai/api/v1',
#         api_key='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'
#     )

# def get_openai_model(client: AsyncOpenAI) -> OpenAIModel:
#     """Initialize and return OpenAI model."""
#     return OpenAIModel(
#         'google/gemini-2.0-flash-lite-preview-02-05:free',
#         # 'gpt-4o-mini',
#         openai_client=client
#     )

def get_llm_model() -> OpenAIModel:
    return OpenAIModel(
        'gpt-4o-mini',
        # base_url='https://openrouter.ai/api/v1',
        api_key=os.getenv('OPENAI_API_KEY')
    )

# def get_llm_model() -> OpenAIModel:
#     return OpenAIModel(
#         'microsoft/phi-3-medium-128k-instruct:free',
#         base_url='https://openrouter.ai/api/v1',
#         api_key='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'
#     )