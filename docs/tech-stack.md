# 技术栈决策

## 产品定位

本项目是一个面向网页端用户的国际化双语铁道支持类 Agent。核心能力包括铁路规章问答、中英术语支持、双语解释、来源引用和多轮对话。

## 前端

- Vue 3
- TypeScript
- Vite
- Vue Router
- Pinia
- Element Plus

选择理由：这是轻量、成熟、适合后台工具和专业问答界面的 Vue 技术组合。第一版不需要 SSR，采用 SPA 即可，降低部署和状态管理复杂度。

## 后端

- Python 3.11 或 3.12
- FastAPI
- Pydantic
- SQLAlchemy 2
- Alembic

选择理由：RAG 文档解析、向量检索、模型调用和数据处理主要集中在 Python 生态中。FastAPI 适合提供流式对话接口、检索接口、术语查询接口和管理接口。

## 数据库

### 对话与业务数据

- PostgreSQL
- 推荐本地开发数据库名：`railway_qa_agent`
- 用户名：`deipss`
- 密码：通过本地 `.env` 配置，不写入仓库

主要表：

- `users`
- `chat_sessions`
- `chat_messages`
- `retrieval_traces`
- `terminology_entries`

### 向量数据

- Qdrant
- 推荐集合名：`railway_knowledge`

向量 payload 保留：

- `source_file`
- `doc_type`
- `heading`
- `chunk_index`
- `language`
- `text`

## 文档处理

- `python-docx` 解析 `.docx`
- 规章文档按标题、条款、段落切分
- 术语表单独抽取为结构化中英词条，不只依赖向量检索

## RAG 流程

1. 识别用户问题语言和意图
2. 先查铁路中英术语库
3. 再查规章知识库
4. 使用向量检索和关键词/术语增强检索
5. 对候选片段 rerank
6. 组织带来源的上下文
7. 调用 LLM 生成双语友好的答案
8. 保存用户消息、助手消息和检索轨迹到 PostgreSQL

## 模型配置

Embedding 默认模型名为 `BAAI/bge-m3`。推荐生产方式是启动一个 OpenAI-compatible embedding 服务，并通过 `EMBEDDING_BASE_URL`、`EMBEDDING_API_KEY`、`EMBEDDING_MODEL` 接入。资源充足时也可以在后端本地安装 CPU 版 PyTorch 与 `sentence-transformers`，由后端直接加载 BGE-M3。

LLM 同样使用 OpenAI-compatible Chat Completions 接口，通过 `LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL` 配置。这样后续可以接 OpenAI、Qwen、DeepSeek、本地 vLLM 或 Xinference 服务。

## 部署

第一版使用 Docker Compose：

- `frontend`
- `backend`
- `postgres`
- `qdrant`

后续如果需要生产部署，再补 Nginx、HTTPS、日志、监控和备份策略。
