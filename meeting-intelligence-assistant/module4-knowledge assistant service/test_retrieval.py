from llama_index.core import Settings

from embedding import get_embedding_model
from ingestion import ingest_meetings
from retrieval import retrieve


Settings.embed_model = get_embedding_model()


MEETING_FILES = [
    "data/sample_meeting1.json",
    "data/sample_meeting2.json"
]


QUERIES = [
    "What is causing the KAS API to be down?",
    "Which vector store did we decide to use?",
    "What is the deadline for our working prototype?",
]


# Ingest ALL meetings first
index = ingest_meetings(MEETING_FILES)


# Then query the shared index
for query in QUERIES:

    print("\n" + "=" * 70)
    print(f"QUERY: {query}")
    print("=" * 70)

    results = retrieve(
        query=query,
        index=index,
        similarity_top_k=3,
    )

    for i, result in enumerate(results):

        print(f"\n--- Result {i + 1} ---")
        print(f"Score: {result.score}")
        print(f"Meeting ID: {result.metadata.get('meeting_id')}")
        print(f"Title: {result.metadata.get('title')}")
        print(f"Text: {result.text}")