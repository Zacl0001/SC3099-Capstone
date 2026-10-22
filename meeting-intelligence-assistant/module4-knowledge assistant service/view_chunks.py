"""Read stored KAS chunks without generating embeddings or changing data."""

import argparse
import json
import sys
import textwrap

import psycopg
from psycopg import sql

if __package__:
    from . import config
else:
    import config


def positive_int(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return number


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--meeting-id", help="Show only this meeting's chunks")
    parser.add_argument("--limit", type=positive_int, default=20, help="Maximum chunks to display (default: 20)")
    parser.add_argument("--metadata", action="store_true", help="Show complete metadata as formatted JSON")
    args = parser.parse_args()

    table = sql.Identifier("public", "data_" + config.POSTGRES_TABLE_NAME.lower())
    where = sql.SQL("")
    parameters = []
    if args.meeting_id is not None:
        where = sql.SQL(" WHERE metadata_->>'meeting_id' = %s")
        parameters.append(args.meeting_id)

    try:
        with psycopg.connect(
            host=config.POSTGRES_HOST, port=config.POSTGRES_PORT,
            dbname=config.POSTGRES_DB, user=config.POSTGRES_USER,
            password=config.POSTGRES_PASSWORD, connect_timeout=5,
        ) as connection:
            connection.read_only = True
            total = connection.execute(
                sql.SQL("SELECT count(*) FROM {}{}").format(table, where), parameters,
            ).fetchone()[0]
            rows = connection.execute(
                sql.SQL("SELECT id, text, metadata_, vector_dims(embedding) FROM {}{} ORDER BY id LIMIT %s").format(table, where),
                [*parameters, args.limit],
            ).fetchall()
    except psycopg.Error as error:
        print(f"Could not read KAS chunks: {error}", file=sys.stderr)
        return 1

    print(f"Database: {config.POSTGRES_DB} | Table: public.data_{config.POSTGRES_TABLE_NAME.lower()}")
    print(f"Showing {len(rows)} of {total} matching chunk(s)")
    if not rows:
        print("No chunks found. Check the meeting ID and whether KAS ingestion completed.")

    for position, (chunk_id, text, metadata, dimensions) in enumerate(rows, 1):
        metadata = metadata or {}
        print("\n" + "=" * 88)
        print(f"CHUNK {position} | Database ID: {chunk_id} | Vector dimensions: {dimensions}")
        print(f"Meeting: {metadata.get('meeting_id', '—')} | Title: {metadata.get('title', '—')}")
        print(f"Date: {metadata.get('meeting_date', '—')} | Start: {metadata.get('meeting_start_time', '—')}")
        print("\nTEXT\n")
        for line in (text or "").splitlines():
            print(textwrap.fill(line, width=88) if line else "")
        if args.metadata:
            print("\nMETADATA\n")
            print(json.dumps(metadata, indent=2, ensure_ascii=False, default=str))
        else:
            sections = metadata.get("section_metadata", [])
            if sections:
                print("\nSOURCE SECTIONS")
                for section in sections:
                    print(f"  {section.get('section_id', '—')} | {section.get('speaker', '—')} | {section.get('timestamp', '—')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
