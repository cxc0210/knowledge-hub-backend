# knowledge-hub-backend

## 启动

```bash
docker compose up -d
docker compose wait ollama-model
uv run alembic upgrade head
uv run fastapi dev main.py
```

`ollama-model` 会在第一次启动时下载 `qwen3-embedding:0.6b`，`docker compose wait` 会等待下载结束。模型和数据库数据都会持久化到 `compose.yaml` 配置的宿主机目录。

如果 Clash/Fake-IP 让 R2 下载域名解析到 `198.18.0.0/15`，可在 `.env` 设置 `OLLAMA_PULL_INSECURE=true`。该开关默认关闭，只影响一次性的模型下载命令；Ollama 仍会校验模型的 SHA-256 摘要。

## AI 接口

在 `.env` 中配置模型 API：

```dotenv
LLM_API_KEY=your-api-key
LLM_MODEL=your-model
# 使用 OpenAI 兼容服务时配置；官方 OpenAI 可省略
LLM_BASE_URL=https://your-provider.example/v1
```

登录后调用 `POST /ai/chat`：

```json
{
  "prompt": "你好，请介绍一下自己"
}
```

接口只把 `prompt` 发给模型，并返回 `{"answer": "..."}`，不会查询数据库、向量库或 Elasticsearch。

流式问答使用 `POST /ai/chat/stream`，请求体相同，响应类型为 `text/event-stream`，并遵循 Vercel AI SDK UI Message Stream v1 协议。可以使用下面的命令验证 Token 是否逐步返回：

```bash
curl -N -X POST 'http://127.0.0.1:8000/ai/chat/stream' \
  -H 'Content-Type: application/json' \
  -b 'kh_access_token=your-token' \
  -d '{"prompt":"请介绍一下 LangGraph"}'
```

## 文档发布与索引

调用 `POST /documents/{document_id}/publish` 后，接口立即返回 `202`，文档状态变为 `INDEXING(45)`，进程内后台 worker 随后执行：

1. 从 MongoDB 读取 Markdown。
2. 按 Markdown 结构和字符数切片（目标 800、最大 1200 字符）。
3. 使用 Qwen3-Embedding-0.6B 生成 1024 维向量。
4. 批量替换 PostgreSQL/pgvector 与 Elasticsearch 中的文档分片。
5. 两边都成功后，将文档更新为 `PUBLISHED(50)`；失败则更新为 `INDEX_FAILED(46)`。

相同正文会生成稳定的 `chunk_id`，重复索引不会累计重复分片。Elasticsearch 的正文和标题使用 IK 中文分析器。

## 检查

```bash
uv run pytest -q
uv run ruff check .
uv run pyright
uv run python -m scripts.check_document_indexing
```

最后一条会创建临时文档，真实验证 MongoDB、Qwen embedding、pgvector 和 Elasticsearch 全链路，并在结束时清理临时数据。
