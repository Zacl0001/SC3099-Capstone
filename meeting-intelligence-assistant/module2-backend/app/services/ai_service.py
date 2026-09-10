# This is an HTTP client to the AI service.
#
# For example:
#
# async def generate_summary(transcript):
#     # POST to ai-service
# Also:
#
# extract_action_items()
# extract_decisions()
# extract_topics()
# Important distinction:
#
# This file should not contain the actual LLM prompting logic.
#
# It calls the AI Processing Service.