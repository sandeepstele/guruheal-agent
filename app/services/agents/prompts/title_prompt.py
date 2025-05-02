def get_system_prompt():
    """
    Returns a simplified system prompt for the title generation agent.
    """
    return """Generate a short, descriptive title for this conversation

REQUIREMENTS:
- Maximum 3 words
- Use title case formatting
- Be specific to the conversation

Return only a JSON object with format: {"title": "Your Title Here"}
""" 