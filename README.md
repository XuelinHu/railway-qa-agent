# Railway QA Agent

Internationalized bilingual railway support RAG system.

## Dataset

Local corpus files are stored under `data/corpus/railway/`.

The `.docx` source documents are ignored by Git because they are large local assets. See `data/corpus/railway/README.md` for the expected files.

## Technology Stack

- Frontend: Vue 3, TypeScript, Vite, Vue Router, Pinia, Element Plus
- Backend: Python, FastAPI, Pydantic, SQLAlchemy 2, Alembic
- Conversation database: PostgreSQL
- Vector database: Qdrant
- Document parsing: python-docx
- Retrieval: bilingual terminology lookup, dense/hybrid vector retrieval, reranking
- Deployment: Docker Compose for local and first production deployment

See `docs/tech-stack.md` for the current stack decision.

## Local Development

Create a local `.env` from `.env.example` and set the PostgreSQL password.

Backend:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

RAG ingestion:

```bash
cd backend
DATABASE_URL="postgresql+asyncpg://deipss:<ENCODED_PASSWORD>@localhost:5432/railway_qa_agent" \
  python scripts/ingest_terminology.py --clear
```

For BGE-M3 embeddings, either configure an OpenAI-compatible embedding service:

```bash
EMBEDDING_BASE_URL="http://localhost:9997/v1" \
EMBEDDING_MODEL="BAAI/bge-m3" \
python scripts/ingest_qdrant.py --recreate
```

Or install local CPU embedding dependencies before running the same script:

```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install sentence-transformers
python scripts/ingest_qdrant.py --recreate
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Infrastructure:

```bash
docker compose up postgres qdrant
```
