from dataclasses import dataclass


@dataclass(frozen=True)
class RetrievalHit:
    text: str
    source_file: str | None = None
    heading: str | None = None
    chunk_index: int | None = None
    score: float | None = None
    kind: str = "document"

    def as_dict(self) -> dict:
        return {
            "text": self.text,
            "source_file": self.source_file,
            "heading": self.heading,
            "chunk_index": self.chunk_index,
            "score": self.score,
            "kind": self.kind,
        }
