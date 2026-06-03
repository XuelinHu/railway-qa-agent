# TODO

更新时间：2026-06-03

## 当前已完成

- 已复制数据集到 `data/corpus/railway/`
  - `README.md`
  - `规章43：ECRL牵引供电设备运行维护管理办法（修订）_zh2en_transResult.docx`
  - `铁路中英文词汇（全）.docx`
- 已搭建前端：Vue 3 + TypeScript + Vite + Pinia + Element Plus
- 已搭建后端：FastAPI + SQLAlchemy async + PostgreSQL
- 已创建 PostgreSQL 数据库：`railway_qa_agent`
- 已抽取并入库铁路中英文术语：`31519` 条
- 已接通聊天接口的术语增强检索
- 已实现 DOCX 解析与切块模块
- 已实现 Qdrant 向量库接入代码和入库脚本
- 已实现 Embedding 抽象层
  - 支持 OpenAI-compatible embedding 服务
  - 支持本地 `sentence-transformers` 加载 `BAAI/bge-m3`
- 已实现 OpenAI-compatible LLM 调用配置
- 已补充 Docker Compose、Dockerfile、`.env.example` 和技术栈文档

## 已验证

```bash
cd backend
../.venv/bin/ruff check .
../.venv/bin/pytest
```

结果：通过，`8 passed`

```bash
cd frontend
npm run build
```

结果：通过

真实语料解析结果：

- 规章文档：`3052 blocks`，`436 chunks`
- 术语文档：`25233 blocks`，`977 chunks`
- 全部 DOCX 汇总切块：`1413 chunks`

术语入库验证：

- `terminology_entries` 表：`31519` 条
- `牵引供电` 可命中：`traction power supply`

## 当前未完成

1. Qdrant 尚未实际启动

   当前 `127.0.0.1:6333` 无服务监听。之前尝试 `docker compose up -d postgres qdrant` 失败，原因是当前用户没有访问 `/var/run/docker.sock` 的权限。

2. Qdrant 向量入库尚未实际执行

   代码和脚本已完成，但需要先启动 Qdrant，再配置 embedding 服务或本地 BGE-M3 模型。

3. BGE-M3 embedding 尚未实际跑通

   已尝试安装 `sentence-transformers`，但默认解析到 CUDA 版 PyTorch 依赖，体积很大，已中止。建议优先使用 OpenAI-compatible embedding 服务承载 `BAAI/bge-m3`。

4. LLM 尚未配置

   当前聊天接口会保存消息、检索术语并返回降级答案。配置 `LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL` 后即可调用真实模型。

## 恢复工作步骤

### 1. 准备环境变量

复制 `.env.example` 为 `.env`，注意密码中的 `@` 在 `DATABASE_URL` 中要写成 `%40`。

```bash
cp .env.example .env
```

建议 `.env` 中至少包含：

```bash
POSTGRES_USER=deipss
POSTGRES_PASSWORD=Java@c1024
POSTGRES_DB=railway_qa_agent
DATABASE_URL=postgresql+asyncpg://deipss:Java%40c1024@127.0.0.1:5432/railway_qa_agent

QDRANT_URL=http://127.0.0.1:6333
QDRANT_COLLECTION=railway_knowledge
RAG_VECTOR_ENABLED=true

EMBEDDING_MODEL=BAAI/bge-m3
EMBEDDING_BASE_URL=
EMBEDDING_API_KEY=

LLM_BASE_URL=
LLM_API_KEY=
LLM_MODEL=
```

### 2. 启动基础服务

如果 Docker 权限已修复：

```bash
docker compose up -d postgres qdrant
```

如果只需要启动 Qdrant，也可以单独启动：

```bash
docker compose up -d qdrant
```

Qdrant 健康检查：

```bash
curl http://127.0.0.1:6333/collections
```

### 3. 启动后端

```bash
cd backend
DATABASE_URL='postgresql+asyncpg://deipss:Java%40c1024@127.0.0.1:5432/railway_qa_agent' \
AUTO_CREATE_TABLES=true \
RAG_VECTOR_ENABLED=true \
../.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```

健康检查：

```bash
curl http://127.0.0.1:8000/api/health
```

### 4. 启动前端

如果 `5173` 被占用，继续用 `5174`：

```bash
cd frontend
npm run dev -- --port 5174
```

访问：

```text
http://127.0.0.1:5174/
```

### 5. 重新入库术语

术语已经入库过。需要重建时执行：

```bash
cd backend
DATABASE_URL='postgresql+asyncpg://deipss:Java%40c1024@127.0.0.1:5432/railway_qa_agent' \
../.venv/bin/python scripts/ingest_terminology.py --clear
```

### 6. 配置 BGE-M3 embedding

推荐方式：启动一个 OpenAI-compatible embedding 服务，模型为 `BAAI/bge-m3`，然后配置：

```bash
EMBEDDING_BASE_URL=http://127.0.0.1:9997/v1
EMBEDDING_MODEL=BAAI/bge-m3
```

再执行：

```bash
cd backend
DATABASE_URL='postgresql+asyncpg://deipss:Java%40c1024@127.0.0.1:5432/railway_qa_agent' \
EMBEDDING_BASE_URL='http://127.0.0.1:9997/v1' \
EMBEDDING_MODEL='BAAI/bge-m3' \
../.venv/bin/python scripts/ingest_qdrant.py --recreate
```

备选方式：本地 CPU 模型。

```bash
cd backend
../.venv/bin/pip install torch --index-url https://download.pytorch.org/whl/cpu
../.venv/bin/pip install sentence-transformers
../.venv/bin/python scripts/ingest_qdrant.py --recreate
```

### 7. 配置 LLM

配置 OpenAI-compatible Chat Completions：

```bash
LLM_BASE_URL=http://127.0.0.1:8001/v1
LLM_API_KEY=your-key
LLM_MODEL=your-chat-model
```

配置后重启后端。

## 烟测命令

术语接口：

```bash
curl 'http://127.0.0.1:8000/api/terminology/search?q=%E7%89%B5%E5%BC%95%E4%BE%9B%E7%94%B5&limit=5'
```

聊天接口：

```bash
curl -s -X POST http://127.0.0.1:8000/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"牵引供电是什么意思？","language":"auto"}'
```

预期至少返回：

```text
牵引供电 = traction power supply
```

## 重点代码位置

- `backend/scripts/ingest_terminology.py`
- `backend/scripts/ingest_qdrant.py`
- `backend/app/rag/terminology_extractor.py`
- `backend/app/rag/embedding.py`
- `backend/app/rag/vector_store.py`
- `backend/app/rag/retriever.py`
- `backend/app/services/chat_service.py`
- `frontend/src/views/ChatView.vue`
- `frontend/src/stores/chat.ts`
