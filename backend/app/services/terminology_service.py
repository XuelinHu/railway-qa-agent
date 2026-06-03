import re

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import TerminologyEntry

CJK_RUN_PATTERN = re.compile(r"[\u4e00-\u9fff]{2,}")
EN_TOKEN_PATTERN = re.compile(r"[A-Za-z][A-Za-z\-']+")
ZH_QUESTION_WORDS = (
    "是什么意思",
    "是什么",
    "什么意思",
    "如何",
    "怎么",
    "怎样",
    "解释",
    "说明",
    "请问",
)
EN_STOPWORDS = {
    "what",
    "is",
    "are",
    "the",
    "a",
    "an",
    "of",
    "for",
    "to",
    "in",
    "and",
    "how",
    "should",
    "please",
    "explain",
}


class TerminologyService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def search(self, query: str, limit: int = 10) -> list[TerminologyEntry]:
        normalized = query.strip()
        if not normalized:
            return []

        search_terms = build_search_terms(normalized)
        if not search_terms:
            return []

        conditions = []
        for term in search_terms[:16]:
            pattern = f"%{term}%"
            conditions.extend(
                [
                    TerminologyEntry.source_term.ilike(pattern),
                    TerminologyEntry.target_term.ilike(pattern),
                ]
            )

        result = await self.db.execute(
            select(TerminologyEntry)
            .where(or_(*conditions))
            .limit(max(limit * 4, limit))
        )
        return rank_terms(normalized, list(result.scalars().all()))[:limit]


def build_search_terms(query: str) -> list[str]:
    terms: list[str] = [query]
    zh_query = query
    for word in ZH_QUESTION_WORDS:
        zh_query = zh_query.replace(word, " ")
    zh_query = re.sub(r"[，。！？、,.!?;:：；()（）]", " ", zh_query)

    for run in CJK_RUN_PATTERN.findall(zh_query):
        terms.append(run)
        if len(run) > 4:
            terms.extend(run[index : index + 4] for index in range(0, len(run) - 3))
            terms.extend(run[index : index + 3] for index in range(0, len(run) - 2))

    english_tokens = [
        token.lower()
        for token in EN_TOKEN_PATTERN.findall(query)
        if token.lower() not in EN_STOPWORDS
    ]
    if english_tokens:
        terms.append(" ".join(english_tokens))
        terms.extend(english_tokens)
        for index in range(0, max(len(english_tokens) - 1, 0)):
            terms.append(" ".join(english_tokens[index : index + 2]))
        for index in range(0, max(len(english_tokens) - 2, 0)):
            terms.append(" ".join(english_tokens[index : index + 3]))

    return unique_terms(terms)


def unique_terms(terms: list[str]) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for term in terms:
        normalized = term.strip().lower()
        if len(normalized) < 2 or normalized in seen:
            continue
        seen.add(normalized)
        unique.append(term.strip())
    return sorted(unique, key=len, reverse=True)


def rank_terms(query: str, entries: list[TerminologyEntry]) -> list[TerminologyEntry]:
    def score(entry: TerminologyEntry) -> tuple[int, int]:
        source = entry.source_term.lower()
        target = entry.target_term.lower()
        lowered_query = query.lower()
        exact_bonus = 10 if source in lowered_query or target in lowered_query else 0
        return exact_bonus, max(len(source), len(target))

    return sorted(entries, key=score, reverse=True)
