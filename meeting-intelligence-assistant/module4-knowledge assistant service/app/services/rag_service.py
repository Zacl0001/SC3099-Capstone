# This is the main conversational pipeline:
#
# Question
#  ↓
# Retrieve chunks
#  ↓
# Build context
#  ↓
# Build prompt
#  ↓
# LLM
#  ↓
# Answer
#  ↓
# Citations
# This is probably the most important file in the Knowledge Service.