from core.ai import get_llm_model
from pydantic_ai import Agent
from app.models.chat import Deps
from app.services.agents.prompts.follow_up_prompt import get_system_prompt
from app.services.agents.tools.schema import FollowUpQuestionsResponse

model = get_llm_model()

follow_agent = Agent(
    model,
    system_prompt=get_system_prompt(),
    deps_type=Deps,
    result_type=FollowUpQuestionsResponse,
    result_retries=3
)
