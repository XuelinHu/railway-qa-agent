import argparse
import asyncio
from pathlib import Path

from app.rag.docx_loader import DocumentChunk, chunk_blocks, load_docx_blocks
from app.rag.embedding import get_embedder
from app.rag.vector_store import QdrantVectorStore, batched

CORPUS_DIR = Path(__file__).resolve().parents[2] / "data" / "corpus" / "railway"


async def ingest(
    corpus_dir: Path,
    recreate: bool,
    limit: int | None,
    batch_size: int,
) -> int:
    chunks = collect_chunks(corpus_dir)
    if limit:
        chunks = chunks[:limit]
    if not chunks:
        return 0

    embedder = get_embedder()
    first_vector = embedder.embed_texts([chunks[0].text])[0]

    store = QdrantVectorStore()
    await store.ensure_collection(vector_size=len(first_vector), recreate=recreate)
    await store.upsert_chunks([chunks[0]], [first_vector])

    total = 1
    for batch in batched(chunks[1:], batch_size):
        vectors = embedder.embed_texts([chunk.text for chunk in batch])
        await store.upsert_chunks(batch, vectors)
        total += len(batch)
        print(f"upserted={total}/{len(chunks)}")

    await store.close()
    return total


def collect_chunks(corpus_dir: Path) -> list[DocumentChunk]:
    chunks: list[DocumentChunk] = []
    for path in sorted(corpus_dir.glob("*.docx")):
        blocks = load_docx_blocks(path)
        chunks.extend(chunk_blocks(blocks, source_file=path.name))
    return chunks


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Embed corpus chunks with BGE-M3 into Qdrant.")
    parser.add_argument("--corpus-dir", type=Path, default=CORPUS_DIR)
    parser.add_argument("--recreate", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--batch-size", type=int, default=16)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    count = asyncio.run(
        ingest(
            corpus_dir=args.corpus_dir,
            recreate=args.recreate,
            limit=args.limit,
            batch_size=args.batch_size,
        )
    )
    print(f"ingested_chunks={count}")


if __name__ == "__main__":
    main()
