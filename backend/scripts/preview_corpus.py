from pathlib import Path

from app.rag.docx_loader import chunk_blocks, load_docx_blocks

CORPUS_DIR = Path(__file__).resolve().parents[2] / "data" / "corpus" / "railway"


def main() -> None:
    for path in sorted(CORPUS_DIR.glob("*.docx")):
        blocks = load_docx_blocks(path)
        chunks = chunk_blocks(blocks, source_file=path.name)
        print(f"{path.name}: {len(blocks)} blocks, {len(chunks)} chunks")


if __name__ == "__main__":
    main()

