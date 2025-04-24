import json
import datetime
from typing import List, Dict, Set, Optional
from pydantic_ai.messages import ModelResponse

def extract_search_data(messages: List[ModelResponse]) -> Optional[Dict]:
    """
    Extract search data from a list of messages, including filter parameters and knowledge base results.
    
    Args:
        messages: List of messages from the agent run
        
    Returns:
        Dictionary containing filter_type, filter_params, and results if a search was performed,
        None otherwise.
    """
    filter_data = None
    knowledge_results = []
    
    # Find the successful tool call and its corresponding return
    tool_call_id = None
    for message in messages:
        for part in message.parts:
            if part.part_kind == 'tool-call':
                filter_data = part.args_as_dict()
                filter_data['filter_type'] = part.tool_name
                if filter_data['filter_type'] != 'web_search':
                    tool_call_id = part.tool_call_id
                break
        
        # Find the tool return in subsequent messages
        if tool_call_id:
            for msg in messages:
                for part in msg.parts:
                    if part.part_kind == 'tool-return' and part.tool_call_id == tool_call_id:
                        response_content = part.content
                        
                        # Handle knowledge base search results
                        if filter_data['filter_type'] == 'knowledge_base_search':
                            if 'results' in response_content:
                                knowledge_results = response_content['results']
                            elif 'documents' in response_content:
                                knowledge_results = response_content['documents']
                            elif 'content' in response_content:
                                knowledge_results = [{"content": response_content['content']}]
    
    if filter_data:
        result_data = {
            "filter_params": filter_data
        }
        
        # Add appropriate results based on filter type
        if filter_data['filter_type'] == 'knowledge_base_search' and knowledge_results:
            result_data["knowledge_results"] = knowledge_results
        
        return result_data
    
    return None
