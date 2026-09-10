# Endpoint:
#
# POST /summarize
# Input:
#
# {
#   "meeting_id": "123",
#   "transcript": "..."
# }
# Output:
#
# {
#   "summary": "...",
#   "key_points": []
# }
# The route should call:
#
# summarization_service
# rather than directly calling the LLM.