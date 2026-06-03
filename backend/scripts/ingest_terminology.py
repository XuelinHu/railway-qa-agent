import argparse
import asyncio
from pathlib import Path

from sqlalchemy import delete

from app.db.session import AsyncSessionLocal
from app.models import TerminologyEntry
from app.rag.terminology_extractor import extract_terms_from_docx

DEFAULT_FILE = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "corpus"
    / "railway"
    / "铁路中英文词汇（全）.docx"
)


async def ingest(path: Path, clear: bool, limit: int | None) -> int:
    terms = extract_terms_from_docx(path, limit=limit)
    async with AsyncSessionLocal() as session:
        if clear:
            await session.execute(
                delete(TerminologyEntry).where(TerminologyEntry.source_file == path.name)
            )
        session.add_all(
            [
                TerminologyEntry(
                    source_term=term.source_term,
                    target_term=term.target_term,
                    source_language=term.source_language,
                    target_language=term.target_language,
                    category=term.category,
                    source_file=term.source_file,
                )
                for term in terms
            ]
        )
        await session.commit()
    return len(terms)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract railway terminology into PostgreSQL.")
    parser.add_argument("--file", type=Path, default=DEFAULT_FILE)
    parser.add_argument("--clear", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    count = asyncio.run(ingest(args.file, clear=args.clear, limit=args.limit))
    print(f"ingested_terms={count}")


if __name__ == "__main__":
    main()
