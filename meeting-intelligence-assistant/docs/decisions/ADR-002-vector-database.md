Explain why you chose:

pgvector
instead of:

Pinecone
Qdrant
Weaviate
etc.
For example:

Decision:
Use PostgreSQL + pgvector.

Reason:
The project already requires PostgreSQL and the expected
dataset is relatively small, so a separate vector database
would add unnecessary infrastructure complexity.