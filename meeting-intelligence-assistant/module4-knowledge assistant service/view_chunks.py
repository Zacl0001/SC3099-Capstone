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
    parser.add_argument("--list-meetings", action="store_true", help="List stored meeting IDs and chunk counts without a meeting filter")
    args = parser.parse_args()

    print(f"Store configured: {config.VECTOR_STORE_TYPE}")
    print(f"Target: {config.POSTGRES_HOST}:{config.POSTGRES_PORT} / {config.POSTGRES_DB} / public.data_{config.POSTGRES_TABLE_NAME.lower()}")
    if config.VECTOR_STORE_TYPE == "simple":
        print("KAS is configured for in-memory storage. This utility reads PostgreSQL, not the running API's memory.", file=sys.stderr)
        return 1

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
            all_total = connection.execute(
                sql.SQL("SELECT count(*) FROM {}").format(table),
            ).fetchone()[0]
            if args.list_meetings:
                meetings = connection.execute(
                    sql.SQL("SELECT metadata_->>'meeting_id', count(*) FROM {} GROUP BY metadata_->>'meeting_id' ORDER BY metadata_->>'meeting_id'").format(table),
                ).fetchall()
                print(f"Total chunks in table: {all_total}")
                for meeting_id, count in meetings:
                    print(f"{meeting_id if meeting_id is not None else '(missing meeting_id)'}: {count} chunk(s)")
                return 0
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
    print(f"Total chunks in table (all meetings): {all_total}")
    if not rows:
        if all_total:
            print("No chunks match this filter. Run with --list-meetings to see the exact stored IDs.")
        else:
            print("This table is empty. Compare the target above with the PostgreSQL settings in your KAS API terminal; processing a transcript does not guarantee ingestion succeeded.")

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
