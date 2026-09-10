# Endpoint:
#
# POST /ingest
# Input:
#
# meeting_id
# transcript
# Pipeline:
#
# Transcript
#  ↓
# Chunking
#  ↓
# Embeddings
#  ↓
# Store vectors