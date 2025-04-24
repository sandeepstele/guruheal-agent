from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import Optional, List

from pydantic import BaseModel
from httpx import AsyncClient
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIModel
from openai import AsyncOpenAI
from dotenv import load_dotenv
import logfire
import gradio as gr

# Load environment variables
load_dotenv()

logfire.configure(token='zmLFCyY7Pzr852mBPwDC9SRNFlDmxGPsxfZ8NRQNDzpY')

# Constants
BASE_URL = "http://cyber-knowledgegraph-rag-microservice.cyber.svc.cluster.local"
API_PATH = f"{BASE_URL}/api/v1/rag"

class QueryRequest(BaseModel):
    query: str
    doc_ids: Optional[List[str]] = ["vamsi_test"]
    group_id: Optional[str] = None

@dataclass
class Deps:
    client: AsyncClient
    rag_base_url: str

# Configure OpenAI client
openai_client = AsyncOpenAI(
    base_url='https://api.dosashop1.com/openai/v1',
    api_key=os.getenv('API_KEY'),
    default_headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {os.getenv('API_KEY')}",
        "api-key": os.getenv('API_KEY')
    }
)

# Initialize the model
model = OpenAIModel(
    'gpt-4o',
    openai_client=openai_client
)

# Create the agent
chat_agent = Agent(
    model,
    system_prompt="""You are a knowledgeable and helpful AI assistant focused on providing accurate and engaging responses.

Core Capabilities:
- You can engage in general conversations on a wide range of topics
- You have access to additional information about documents through your knowledge retrieval ability, you can use the query_rag tool to retrieve information about the documents, user has already provided document that can be accessed via query_rag tool
- You seamlessly incorporate any retrieved information into your responses

Interaction Style:
- Be natural and conversational while maintaining professionalism
- Provide comprehensive yet concise responses
- Be direct in your answers without explaining your internal processes
- Stay focused on the user's needs and questions

Information Retrieval Strategy:
- When searching for information, formulate comprehensive queries that:
  * Address the immediate question in detail
  * Gather context for potential follow-up questions
  * Cover related aspects of the topic
- Always aim to retrieve enough context to provide thorough, well-informed responses
- Use the retrieved information naturally in your responses without mentioning the retrieval process

Response Guidelines:
- When users ask about document-specific information, naturally incorporate relevant details into your response
- For general queries, draw from your broad knowledge base
- Always aim to provide the most accurate and helpful information possible
- Maintain a consistent, friendly tone throughout the conversation
- Be prepared to elaborate on any aspect of your responses

Remember: Your goal is to be helpful and informative while keeping the interaction natural and engaging.""",
    deps_type=Deps
)

# Configure logfire
logfire.configure(send_to_logfire='if-token-present')

@chat_agent.tool
async def query_rag(ctx: RunContext[Deps], query: str) -> dict:
    """Query the RAG service to retrieve relevant document information.
    
    Formulate your query to:
    1. Capture the core information needed to answer the user's question
    2. Include relevant context that might help with follow-up questions
    3. Be specific enough to get precise information but broad enough to get useful context
    
    Args:
        ctx: The context containing dependencies
        query: A comprehensive search query that will help answer the user's question
            and anticipate follow-ups. Make the query detailed and specific.
    """
    logfire.info("Agent tool call", 
        query=query,
        tool="query_rag"
    )

    print(f"Querying RAG with query: {query}")

    request = QueryRequest(
        query=query,
        doc_ids=["vamsi_test"]
    )
    
    with logfire.span('RAG Query', params={
        'query': query,
        'doc_ids': request.doc_ids,
        'endpoint': f"{ctx.deps.rag_base_url}/api/v1/rag/query"
    }) as span:
        try:
            response = await ctx.deps.client.post(
                f"{ctx.deps.rag_base_url}/api/v1/rag/query",
                json=request.model_dump(),
            )
            response.raise_for_status()
            result = response.json()
            
            span.set_attribute('response_status', response.status_code)
            span.set_attribute('response_data', result)
            
            return result
        except Exception as e:
            span.set_status('error', str(e))
            logfire.error("RAG query failed", 
                error=str(e),
                query=query,
                doc_ids=request.doc_ids
            )
            return {
                "error": "Failed to retrieve additional context",
                "context": "I apologize, but I'm having trouble accessing the document at the moment. Please try asking your question again, and I'll do my best to help."
            }

async def process_message(message: str, chat_history: List[tuple], state: Optional[dict] = None) -> tuple[str, List[tuple], dict]:
    """Process a single message using the existing chat agent logic."""
    if state is None:
        state = {"previous_result": None}
        
    async with AsyncClient(timeout=30.0) as client:
        deps = Deps(
            client=client,
            rag_base_url=BASE_URL
        )
        
        try:
            # Get agent's response using existing logic
            result = await chat_agent.run(
                message, 
                deps=deps,
                message_history=state["previous_result"].all_messages() if state["previous_result"] else None
            )
            
            # Store result for next iteration
            state["previous_result"] = result
            
            # Log agent's response
            logfire.info("Agent response",
                response=result.data
            )
            
            # Update chat history
            chat_history.append((message, result.data))
            return result.data, chat_history, state
            
        except Exception as e:
            logfire.error("Chat error",
                error=str(e),
                user_input=message
            )
            error_message = f"An error occurred: {str(e)}"
            chat_history.append((message, error_message))
            return error_message, chat_history, state

def create_gradio_interface():
    """Create and configure the Gradio interface with enhanced UI features."""
    
    # Define custom theme with corrected properties
    theme = gr.themes.Soft(
        primary_hue="blue",
        secondary_hue="gray",
        neutral_hue="gray",
        font=["Helvetica", "ui-sans-serif", "system-ui", "sans-serif"]
    )

    with gr.Blocks(theme=theme, css="""
        .container { max-width: 800px; margin: auto; padding: 20px; }
        .chatbot { height: 500px; overflow-y: auto; }
        .message-box { min-height: 60px; }
        .button-row { display: flex; gap: 10px; }
        .chatbot .message.bot { 
            background-color: #f3f4f6; 
            border-radius: 12px;
            padding: 12px 16px;
            margin: 8px 0;
        }
        .chatbot .message.user { 
            background-color: #e3e8ff;
            border-radius: 12px;
            padding: 12px 16px;
            margin: 8px 0;
        }
        .chatbot .avatar-image {
            width: 32px !important;
            height: 32px !important;
            margin-right: 12px;
        }
        code { 
            background-color: #f0f0f0; 
            padding: 2px 4px; 
            border-radius: 4px; 
            font-family: monospace;
        }
    """) as interface:
        gr.Markdown("""
            # AI Chat Assistant
            Ask me anything! I can help answer your questions using my knowledge base.
        """)
        
        with gr.Column(elem_classes="container"):
            chatbot = gr.Chatbot(
                label="Chat History",
                elem_classes="chatbot",
                height=500,
                show_label=False,
                bubble_full_width=False,
                avatar_images=(
                    "https://api.dicebear.com/7.x/avataaars/svg?seed=user",  # User avatar
                    "https://api.dicebear.com/7.x/bottts/svg?seed=assistant"  # Assistant avatar
                )
            )
            
            with gr.Row():
                msg = gr.Textbox(
                    label="Your message",
                    placeholder="Type your message here...",
                    elem_classes="message-box",
                    show_label=False,
                    container=False,
                    scale=9
                )
                submit = gr.Button(
                    "Send",
                    variant="primary",
                    scale=1
                )
            
            with gr.Row(elem_classes="button-row"):
                clear = gr.Button("Clear Chat", variant="secondary")
                regenerate = gr.Button("Regenerate", variant="secondary")
                
            # Example questions to help users get started
            gr.Examples(
                examples=[
                    "What can you tell me about the documents you have access to?",
                    "How can you help me today?",
                    "Tell me about the main topics covered in the documents."
                ],
                inputs=msg,
                label="Try these examples"
            )
        
        # Initialize state
        state = gr.State({"previous_result": None})
        
        # Handle message submission
        submit_click = submit.click(
            fn=process_message,
            inputs=[msg, chatbot, state],
            outputs=[msg, chatbot, state],
            api_name="submit"
        ).then(
            fn=lambda: "",
            inputs=None,
            outputs=msg
        )
        
        # Also trigger submission on Enter
        msg.submit(
            fn=process_message,
            inputs=[msg, chatbot, state],
            outputs=[msg, chatbot, state],
        ).then(
            fn=lambda: "",
            inputs=None,
            outputs=msg
        )
        
        # Handle clear button
        clear.click(
            fn=lambda: ([], {"previous_result": None}),
            inputs=None,
            outputs=[chatbot, state],
            api_name="clear"
        )
        
        # Handle regenerate button
        def regenerate_response(chat_history, state):
            if not chat_history:
                return chat_history, state
            last_user_message, _ = chat_history[-1]
            chat_history = chat_history[:-1]  # Remove last exchange
            return process_message(last_user_message, chat_history, state)
        
        regenerate.click(
            fn=regenerate_response,
            inputs=[chatbot, state],
            outputs=[chatbot, state],
            api_name="regenerate"
        )
        
    return interface

def main():
    """Entry point of the application."""
    interface = create_gradio_interface()
    interface.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=True
    )

if __name__ == "__main__":
    main()