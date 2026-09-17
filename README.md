# Railway QA Agent

<p align="center">
  <img height="20" src="https://img.shields.io/badge/vue-3.5.13-42B883?logo=vuedotjs&amp;logoColor=white" />
  <img height="20" src="https://img.shields.io/badge/typescript-5.7.2-3178C6?logo=typescript&amp;logoColor=white" />
  <img height="20" src="https://img.shields.io/badge/fastapi-0.115%2B-009688?logo=fastapi&amp;logoColor=white" />
  <img height="20" src="https://img.shields.io/badge/sqlalchemy-2.0.40%2B-D71F00?logo=sqlalchemy&amp;logoColor=white" />
  <img height="20" src="https://img.shields.io/badge/postgresql-used-4169E1?logo=postgresql&amp;logoColor=white" />
  <img height="20" src="https://img.shields.io/badge/qdrant-1.14%2B-DC244C" />
  <img height="20" src="https://img.shields.io/badge/docker_compose-configured-2496ED?logo=docker&amp;logoColor=white" />
</p>

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

<!-- codex-runtime-notes:start -->

## Runtime Ports And Database Configuration

### Database
- Conversation/application database: PostgreSQL.
- Default database name: `railway_qa_agent`.
- Default PostgreSQL port: `5432`.
- Default URL pattern: `postgresql+asyncpg://deipss:<YOUR_PASSWORD>@localhost:5432/railway_qa_agent`.
- Vector database: Qdrant.
- Default Qdrant collection: `railway_knowledge`.
- Default Qdrant ports: HTTP `6333`, gRPC `6334`.

### Default Ports
- Backend FastAPI service: `8025`.
- Frontend Vite dev server: `4023`.
- PostgreSQL: `5432`.
- Qdrant: `6333` and `6334`.

### Notes
- Encode special characters in the PostgreSQL password inside `DATABASE_URL`, for example `@` as `%40`.

### Source Files Checked
- `.env.example`
- `docker-compose.yml`
- `backend/app/core/config.py`
- `frontend/vite.config.ts`

<!-- codex-runtime-notes:end -->
