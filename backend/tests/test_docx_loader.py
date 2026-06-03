from app.rag.docx_loader import DocumentBlock, chunk_blocks, normalize_text


def test_normalize_text() -> None:
    assert normalize_text("  牵引\u3000供电   equipment ") == "牵引 供电 equipment"


def test_chunk_blocks_keeps_source_metadata() -> None:
    blocks = [
        DocumentBlock(text="Chapter 1", block_type="heading", heading="Chapter 1", index=0),
        DocumentBlock(text="A" * 50, block_type="paragraph", heading="Chapter 1", index=1),
        DocumentBlock(text="B" * 50, block_type="paragraph", heading="Chapter 1", index=2),
    ]

    chunks = chunk_blocks(blocks, source_file="rules.docx", max_chars=80, overlap_chars=5)

    assert len(chunks) == 2
    assert chunks[0].source_file == "rules.docx"
    assert chunks[0].heading == "Chapter 1"

