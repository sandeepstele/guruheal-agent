from core.ai import get_llm_model
from pydantic_ai import Agent, RunContext
from app.models.chat import Deps
from app.services.agents.prompts.metadata_prompt import get_system_prompt
from app.services.agents.tools.schema import MetadataResponse

model = get_llm_model()

metadata_agent = Agent(
    model,
    system_prompt=get_system_prompt(),
    deps_type=Deps,
    result_type=MetadataResponse,
    result_retries=3
) 

# Add dynamic system prompt for multilingual support
@metadata_agent.system_prompt
def add_language_instructions(ctx: RunContext[Deps]) -> str:
    instructions = []
    
    # Language instructions
    language = ctx.deps.language
    if language and language.lower() != 'en':
        language_map = {
            'hi': 'Hindi',
            'ta': 'Tamil',
            'te': 'Telugu',
            'kn': 'Kannada'
        }
        
        language_name = language_map.get(language.lower(), "")
        if language_name:
            instructions.append(f"""
IMPORTANT LANGUAGE INSTRUCTION:
- Generate follow-up questions in {language_name} language.
- Continue to check for appointment booking intent in the conversation regardless of language.
- The phrase "Find the appointment booking link below" might be in {language_name} in the conversation, so look for equivalent phrases.
""")
    
    # Web search related follow-up questions
    if ctx.deps.use_web_search:
        instructions.append("""
IMPORTANT FOLLOW-UP QUESTION INSTRUCTION:
- Since the user requested web search, include at least one follow-up question related to the web search results.
- Make sure the follow-up questions encourage the user to explore more up-to-date information that might be available via web search.
""")
    
    return "".join(instructions) 