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

## Accounts And Roles

Sign-in is required to use the application. The first backend start creates one
account — `BOOTSTRAP_ADMIN_USERNAME` (default `admin`) with
`BOOTSTRAP_ADMIN_PASSWORD` — flagged as *must change password*, so the first
sign-in goes straight to the profile page.

- Registration, sign-in, sign-out, password change, profile editing.
- Forgotten passwords: with SMTP configured a reset link is mailed. Without it
  the request is recorded and an administrator issues a reset token from
  用户管理, so the flow never silently pretends to have sent mail.
- Access tokens live two hours and are held in memory only; the refresh token is
  an HttpOnly cookie scoped to `/api/auth`, so a page reload re-establishes the
  session and a cross-site script cannot read either token.
- Permissions are a code-level registry (`backend/app/core/permissions.py`).
  A role is a named set of permission codes, and the admin sidebar is built
  from the permissions the signed-in account actually holds — a role change
  cannot leave a dead link behind.

## Administration Console

The sidebar is 概览 plus five management menus, and every list in them is
paginated and filterable through the same `Page[T]` envelope and the same
front-end table components:

| Menu | What it does |
| --- | --- |
| 概览 | Counts of users, conversations, messages, terminology; model status |
| 用户管理 | Search, create, edit, enable/disable, assign roles, reset passwords, handle forgotten-password requests |
| 角色权限 | Roles and their permission tree; system roles are protected from deletion |
| 对话与消息 | Every conversation with its messages and the retrieval trace behind each answer |
| 术语库管理 | 31k+ bilingual terms: search both directions, edit, delete, bulk import from a file |
| 模型管理 | The Ollama catalogue: list, switch the active model, load/unload, pull online with live progress, delete |

## The Agent

A floating button in the bottom-right corner (also `Alt+K`) opens the agent over
whatever page you are on — it is mounted in both the user and admin layouts.

- Answers stream token by token over SSE, with the retrieval citations listed
  underneath and the model's reasoning in a collapsible block when it produces
  any. Reloading the page brings the whole conversation back, reasoning included.
- Voice output, and voice input for a hands-free back-and-forth. The browser's
  own Web Speech engines are preferred; when they are missing the server-side
  engines are used instead. Speak while an answer is being read out and it stops
  — you can interrupt it.
- The model picker in the panel header switches the active model for everyone,
  if your account holds `model:switch`.

> **Microphone access needs a secure context.** Browsers only grant
> `getUserMedia` and `SpeechRecognition` on `https://` or `localhost`. Opening
> the app over plain HTTP from another host — including through the FRP tunnel
> (see the port notes below) — disables voice input, and the interface says so
> rather than failing silently. Serve the app over HTTPS (a reverse proxy such
> as Caddy with a certificate will do) or use it from `localhost` for voice.

Server-side speech is optional and installed separately. Without it the app runs
normally and uses the browser engines:

```bash
cd backend
pip install -e ".[speech]"
```

## Model Management

Ollama is expected on the host at `OLLAMA_BASE_URL` (default
`http://127.0.0.1:11434`). `LLM_PROVIDER=auto` routes to Ollama when the base
URL looks like one and to any OpenAI-compatible endpoint otherwise, so a
deployment without a local model server still works.

Only models this application loaded are ever unloaded. On a GPU shared with
other work, evicting someone else's model is a denial of service, so unloading a
model the app did not load is refused unless it is explicitly forced.

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
- Tables are created from the ORM metadata on startup (`AUTO_CREATE_TABLES`). The accounts work added `roles`, `role_permissions`, `user_roles`, `user_tokens`, `password_reset_requests`, `system_settings`, `model_events` and `audit_logs`, and extended `users` with credentials, profile and lockout columns. Existing rows, including the terminology corpus, are preserved.
- Both ports fall inside the FRP range that is forwarded to the public internet. Anyone with the address can reach the app there, over plain HTTP — so set a real `JWT_SECRET`, change the bootstrap administrator password, and expect the browser to refuse microphone access on that origin.

### Source Files Checked
- `.env.example`
- `docker-compose.yml`
- `backend/app/core/config.py`
- `backend/app/core/permissions.py`
- `backend/pyproject.toml`
- `frontend/vite.config.ts`

<!-- codex-runtime-notes:end -->
