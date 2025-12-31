# Logos - 个人 AI 操作系统基础

基于 Docker Compose 构建的高代码 AI 助手系统，采用 Open WebUI 作为前端、LiteLLM 作为 API 网关、PostgreSQL + pgvector 作为向量数据库。

## 架构

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Open WebUI    │────▶│    LiteLLM      │────▶│    AI 服务商    │
│   (端口 3000)   │     │   (端口 4000)   │     │ Gemini/Claude/  │
│                 │     │                 │     │ OpenAI          │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                               │
                               ▼
                        ┌─────────────────┐
                        │   PostgreSQL    │
                        │   + pgvector    │
                        │   (端口 5432)   │
                        └─────────────────┘
```

## 环境要求

- Docker Engine 24+
- Docker Compose v2

## 快速开始

```bash
# 启动服务
./scripts/init.sh up

# 检查健康状态
./scripts/init.sh health

# 查看日志
./scripts/init.sh logs

# 停止服务
./scripts/init.sh down
```

## 服务列表

| 服务 | 端口 | 说明 |
|------|------|------|
| Open WebUI | 3000 | AI 对话界面 |
| LiteLLM | 4000 | 多模型 API 网关 |
| PostgreSQL | 5432 | 向量数据库 (pgvector) |

## 配置

### API 密钥

**方式一：使用 .env 文件（推荐）**

```bash
cd infra
cp .env.example .env
# 编辑 .env 填入你的 API 密钥
```

**方式二：使用环境变量**

```bash
export GEMINI_API_KEY="your-gemini-key"
export ANTHROPIC_API_KEY="your-anthropic-key"  # 可选
export OPENAI_API_KEY="your-openai-key"        # 可选
```

> 环境变量优先级高于 .env 文件

### 模型配置

编辑 `infra/litellm_config.yaml` 添加或修改模型。

## 项目结构

```
Logos/
├── src/                    # LangGraph 应用代码 (待开发)
├── infra/                  # Docker 基础设施
│   ├── docker-compose.yml
│   ├── litellm_config.yaml
│   └── init-pgvector.sql
├── scripts/
│   └── init.sh             # 服务管理脚本
└── README.md
```

## 后续计划

- [ ] 在 `/src` 中实现 LangGraph 智能体
- [ ] 通过 API 连接智能体到 LiteLLM
- [ ] 使用 PostgreSQL 存储对话历史
- [ ] 基于 pgvector 实现 RAG
