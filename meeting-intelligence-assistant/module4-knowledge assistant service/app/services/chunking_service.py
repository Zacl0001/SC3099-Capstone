# This is one of the most important RAG files.
#
# Input:
#
# long transcript
# Output:
#
# chunk 1
# chunk 2
# chunk 3
# ...
# But preserve metadata:
#
# {
#     "text": "...",
#     "start_time": "...",
#     "end_time": "...",
#     "speaker": "John"
# }
# Experiment with chunk sizes later.
#
# For example:
#
# 500 tokens
# 800 tokens
# 1000 tokens