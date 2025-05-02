from core.ai import get_llm_model
from pydantic_ai import Agent, RunContext
from app.models.chat import Deps
from app.services.agents.prompts.title_prompt import get_system_prompt
from app.services.agents.tools.schema import TitleResponse

model = get_llm_model()

title_agent = Agent(
    model,
    system_prompt=get_system_prompt(),
    deps_type=Deps,
    result_type=TitleResponse,
    result_retries=3
) 