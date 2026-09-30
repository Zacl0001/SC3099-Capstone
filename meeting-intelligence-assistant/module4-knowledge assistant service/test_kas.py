from pathlib import Path

from ingestion import find_meeting_files
from service import KnowledgeAssistant


def print_results(response: dict) -> None:
    """Print search results in a readable format."""
    print("\n" + "=" * 80)
    print(f"QUERY: {response['query']}")
    print("=" * 80)

    results = response["results"]

    if not results:
        print("No results found.")
        return

    print(f"\nRetrieved {len(results)} result(s).\n")

    for i, result in enumerate(results, start=1):
        print("-" * 80)
        print(f"RESULT {i}")
        print("-" * 80)

        print(f"Score:       {result['score']}")
        print(f"Meeting ID:  {result['meeting_id']}")
        print(f"Title:       {result['title']}")
        print(f"Date:        {result['meeting_date']}")
        print(f"Start Time:  {result['meeting_start_time']}")
        print(f"Speakers:    {', '.join(result['speakers'])}")

        print("\nText:")
        print(result["text"])

        print("\nSource Sections:")

        section_metadata = result.get("section_metadata", [])

        if not section_metadata:
            print("  No section metadata")
        else:
            for section in section_metadata:
                print(
                    f"  - {section['section_id']} | "
                    f"{section['speaker']} | "
                    f"{section['timestamp']}"
                )

        print()


def main() -> None:
    data_directory = Path("data")

    # ------------------------------------------------------------------
    # 1. Initialize Knowledge Assistant
    # ------------------------------------------------------------------

    print("Initializing Knowledge Assistant...")

    assistant = KnowledgeAssistant(
        similarity_top_k=5
    )

    print("Knowledge Assistant initialized.")

    # ------------------------------------------------------------------
    # 2. Find meeting files
    # ------------------------------------------------------------------

    print("\nFinding meeting files...")

    meeting_files = find_meeting_files(data_directory)

    if not meeting_files:
        print("No meeting JSON files found.")
        return

    print(f"Found {len(meeting_files)} meeting file(s):")

    for file_path in meeting_files:
        print(f"  - {file_path}")

    # ------------------------------------------------------------------
    # 3. Ingest meetings
    # ------------------------------------------------------------------

    print("\nIngesting meetings...")

    assistant.ingest(meeting_files)

    print("Ingestion complete.")

    # ------------------------------------------------------------------
    # 4. Search
    # ------------------------------------------------------------------

    queries = [
        "Why was the database connection limit being exhausted?",
        "What caused the KAS API to return 500 errors?",
        "What was the solution to the database connection problem?",
    ]

    for query in queries:
        response = assistant.search(query)
        print_results(response)


if __name__ == "__main__":
    main()
