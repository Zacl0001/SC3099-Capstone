import json
from llama_index.core.node_parser import (
    SentenceSplitter,
    SentenceWindowNodeParser,
    SemanticSplitterNodeParser,
)
from llama_index.core.schema import Document
from llama_index.embeddings.ollama import OllamaEmbedding
import os

# --- 1. Load your Data ---
file_name = "../data/sample_meeting.json"

if not os.path.exists(file_name):
    print(f"Error: The file '{file_name}' was not found.")
    print("Please make sure the JSON files are in the same directory as this script.")
else:
    with open(file_name, 'r') as f:
        meeting_data = json.load(f)

    # Combine the text from all sections into a single string for chunking.
    # A more advanced approach would be to create a Document for each section
    # and attach metadata before chunking.
    full_transcript_text = "\n".join(
        [f"{section['speaker_name']}: {section['text']}" for section in meeting_data['sections']]
    )
    
    document = Document(
        text=full_transcript_text,
        metadata={
            "meeting_id": meeting_data["meeting_id"],
            "title": meeting_data["title"]
        }
    )
    
    print("--- Original Document Text ---")
    print(document.text)
    print("-" * 30 + "\n")


    # --- 2. Define and Apply Chunking Strategies ---

    def print_chunks(title, chunks):
        """Helper function to print the results of a chunking strategy."""
        print(f"--- Strategy: {title} ---")
        print(f"Number of chunks: {len(chunks)}")
        for i, chunk in enumerate(chunks):
            print(f"Chunk {i+1}:")
            # The actual text is in chunk.text
            print(chunk.text) 
            print("---")
        print("\n" + "="*50 + "\n")

    # Strategy 1: SentenceSplitter (Standard Approach)
    # Splits by sentence and groups into chunks of a fixed size with overlap.
    splitter_standard = SentenceSplitter.from_defaults()
    chunks_standard = splitter_standard.get_nodes_from_documents([document])
    print_chunks("Standard SentenceSplitter", chunks_standard)

    # Strategy 2: SentenceWindowNodeParser
    # Each node contains a "window" of text, with surrounding sentences in metadata.
    # This provides more context to the LLM during retrieval.
    node_parser_window = SentenceWindowNodeParser.from_defaults()
    nodes_window = node_parser_window.get_nodes_from_documents([document])
    
    # We'll just print the main text of each window node for comparison here.
    # In a real RAG app, you'd use the text in `node.metadata['window']`.
    print_chunks("SentenceWindowNodeParser", nodes_window)

    # Strategy 3: SemanticSplitterNodeParser
    # Uses an embedding model to find semantic breaks in the text.
    # This is great for creating topically coherent chunks.
    print("Initializing Semantic Splitter... (This might take a moment)")
    embed_model = OllamaEmbedding(model_name="nomic-embed-text")
    splitter_semantic = SemanticSplitterNodeParser.from_defaults(embed_model=embed_model)
    
    chunks_semantic = splitter_semantic.get_nodes_from_documents([document])
    print_chunks("SemanticSplitterNodeParser", chunks_semantic)

