# Agent Instructions

## Default Conda Environment
- Environment name: `rc-llm-eval`
- Environment path: `/home/xuelin/miniconda3/envs/rc-llm-eval`
- Prefer running Python commands with `conda run -n rc-llm-eval ...` or `/home/xuelin/miniconda3/envs/rc-llm-eval/bin/python`.

<!-- codex-agent-runtime:start -->

## Runtime Ports And Database Configuration

- Keep this section aligned with the root README when database names, ports, or service defaults change.
- Do not copy secrets from local `.env` files into commits; document only placeholders or compose defaults.

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

### Notes For Codex Agents
- Encode special characters in the PostgreSQL password inside `DATABASE_URL`, for example `@` as `%40`.
- Before committing, check `git status --short --branch` and avoid staging unrelated runtime artifacts.

### Source Files Checked
- `.env.example`
- `docker-compose.yml`
- `backend/app/core/config.py`
- `frontend/vite.config.ts`

<!-- codex-agent-runtime:end -->

## GitHub Commit Language

- Use English for all GitHub commit messages and pull/push related commit notes.
