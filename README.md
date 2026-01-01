# Logos - 个人 AI 操作系统基础

基于 Docker Compose 构建的高代码 AI 助手系统，采用 Open WebUI 作为前端、LiteLLM 作为 API 网关、PostgreSQL + pgvector 作为底层存储，并集成了强大的 **LangGraph** 多智能体工作流。

## 核心特性

- **多智能体联邦 (LangGraph Federation)**:
  - **TRPG GM**: 具备对抗式工作流（Storyteller + Rules Lawyer）的专业跑团主持人。
  - **Writer**: 小说家与编剧模式，支持 StoryBible 设定集维护与 Reflexion 循环优化。
  - **Coach/Psychologist**: 具备并行用户画像建模与危机干预能力的心理疏导与教练。
  - **Researcher/Coder**: 共享 RAG 引擎，支持大规模文档与代码库的精准检索。
- **Gemini-Distill 视觉解析 Engine**: 专为规则书与复杂文档设计的视觉解析引擎，支持结构化 JSON 提取。
- **抗幻觉术语系统 (Glossary Editor)**: 全局术语表硬性约束，确保 AI 输出术语一致性。
- **数据持久化**: 基于 PostgreSQL + pgvector 实现的长短期记忆、向量检索与对话状态存盘。

## 架构

## 架构

```mermaid
graph TD
    UI[Frontend (Chainlit/Streamlit)] --> Gateway[FastAPI Gateway]
    Gateway --> AG[LangGraph Agents]
    AG --> DB[(PostgreSQL + pgvector)]
    AG --> LLM[Gemini/Claude/OpenAI]
```

## 服务列表

| 服务 | 端口 | 说明 |
|------|------|------|
| Chainlit UI | 8000 | AI 对话界面与可视化 |
| LiteLLM | 4000 | 多模型 API 网关 |
| PostgreSQL | 5432 | 向量数据库 |

## 项目结构

```
Logos/
├── backend/                # 核心逻辑
│   ├── gateway/            # 应用入口与生命周期管理
│   ├── agents/             # 智能体业务逻辑
│   ├── database/           # 数据模型
│   └── utils/              # 通用工具
├── frontend/
│   └── chainlit/           # Chainlit 对话主界面 (含骰子工具)
├── infra/                  # Docker 配置
└── scripts/                # 管理脚本
```

## 开发与扩展

本项目采用 `uv` 进行依赖管理。
- 添加依赖: `uv add <package>`
- 运行测试: `uv run pytest`
- 数据库迁移: `alembic revision --autogenerate -m "description"` 然后 `alembic upgrade head`
