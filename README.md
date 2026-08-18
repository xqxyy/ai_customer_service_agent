# AI Customer Service Agent

一个面向客服业务场景的 AI Agent 工程化项目。项目围绕“用户咨询、知识库检索、工具调用、风险拦截、工单流转、过程追踪”搭建，重点展示智能客服系统从问答到业务处理的完整后端链路。

## 项目定位

这个项目不是单纯的聊天机器人，而是一个可运行的客服运营平台原型。它通过 FastAPI 提供接口和工作台页面，通过 LangChain Agent 组织模型与工具调用，通过 Milvus 做知识库语义检索，通过 PostgreSQL 保存会话、工单、工具调用和 Agent 运行记录。

项目适合作为 AI 应用工程化、RAG、Agent 工具调用、数据库建模和可观测链路的作品集示例。

## 技术栈

- 后端框架：FastAPI
- Agent 编排：LangChain
- 大模型服务：DeepSeek 兼容接口
- Embedding：SiliconFlow BGE-M3
- 向量数据库：Milvus
- 业务数据库：PostgreSQL
- ORM 与迁移：SQLAlchemy、Alembic
- 前端工作台：FastAPI Static Files 原生页面
- 本地依赖编排：Docker Compose

## 核心能力

- 多轮客服对话入口
- RAG 知识库检索
- 订单、客户、工单等业务工具调用
- 高风险问题前置识别
- 投诉、赔偿、隐私、账号安全等场景自动进入人工审核
- Agent run、工具调用、引用来源、消息记录持久化
- Agent Run 观测字段：模型、耗时、失败类型、RAG 命中、工具数量和工单创建状态
- 统一 Tool Calling 返回结构，支持参数校验、结构化错误码和调用耗时追踪
- 演示工作台展示聊天结果、工单状态、RAG 来源、Prompt 模板、Agent Trace 和评估报告
- RAG 评估、Agent 端到端评估与公开客服数据样本转换脚本

## 模块结构

- `backend/app/agents`：Agent 主流程
- `backend/app/core`：配置管理
- `backend/app/db`：ORM 模型、数据库连接、查询服务
- `backend/app/evals`：Agent 端到端评估和评估报告读取
- `backend/app/prompts`：Agent 角色、工具路由、RAG 边界和高风险转人工 Prompt 模板
- `backend/app/rag`：知识库文档加载、切块、检索
- `backend/app/schemas`：API 请求和响应结构
- `backend/app/services`：风险识别等业务服务
- `backend/app/static`：本地工作台页面
- `backend/app/tools`：Agent 可调用工具、统一工具返回结构和工具规格注册表
- `scripts`：数据准备、RAG 入库、公开数据转换、评估脚本和评估报告生成
- `migrations`：Alembic 数据库迁移
- `data`：示例知识库、处理后文档、评估集
- `docs`：项目补充说明

## 系统流程

用户通过 `/chat` 提交问题后，后端会创建一次 Agent run，并保存用户消息。系统先进行高风险规则识别，如果命中投诉、赔偿、隐私、账号安全等场景，会直接创建人工审核工单。普通问题进入 LangChain Agent，由模型根据工具描述决定是否查询知识库、订单、客户信息或创建工单。

知识库检索使用 Milvus 保存文档切块向量，并在回答中返回可追踪的来源信息。所有关键过程会同步写入 PostgreSQL，便于后续在工作台中查看消息、工单、工具调用和引用依据。每次 Agent run 还会记录模型名、模型提供方、总耗时、失败类型、RAG 是否命中、RAG 最高分、工具调用数量和是否创建工单，方便复盘和优化。

## Demo 展示

本地工作台提供三类演示场景：

- 普通政策问题：展示 RAG 检索、引用来源和回答边界
- 订单/客户问题：展示 Agent 工具调用、统一工具返回结构和结构化 Trace
- 高风险问题：展示投诉、赔偿、账号异常等场景自动转人工审核

工作台还提供 Prompt 模板视图，用于展示 Agent 角色边界、工具路由策略、RAG 依据约束、高风险转人工规则和客服回复格式。

工作台的 Trace 摘要可以跳转到 Agent Run 详情页，查看一次请求的用户问题、最终回答、工具入参、工具返回、RAG 来源、耗时和失败类型。评估视图会读取最近一次 RAG eval 和 Agent eval 报告，展示通过率、Top1/Top3 命中率和状态分布。

## 数据与知识库

项目包含一套示例知识库，并支持从 Markdown、TXT、JSON、PDF、扫描 PDF 等来源整理为统一文档格式，再切块写入 Milvus。公开数据集相关脚本用于本地扩展测试数据，不会把大体积原始数据直接提交到仓库。

仓库中不包含真实密钥、本地数据库、日志、Word 文档和私有复习资料。

## 本地运行

本地运行需要准备 Python 环境、Docker Desktop 和模型 API Key。首次运行前复制 `.env.example` 为 `.env`，填写 DeepSeek 与 SiliconFlow API Key。

Windows 下可以直接一键启动：

```powershell
.\start_project.bat
```

脚本会启动 Docker Compose 依赖、执行 Alembic 数据库迁移、启动 FastAPI 后端，并打开工作台页面。

如果修改了知识库文件，需要重建 RAG：

```powershell
.\start_project.bat -RebuildRag
```

如果只想重新生成 RAG 评估报告：

```powershell
python -m scripts.run_rag_eval
```

报告会写入 `data/processed/rag_eval_report.json`。Agent 端到端评估报告由下面命令生成：

```powershell
python -m backend.app.evals.run_customer_service_eval
```

报告会写入 `data/processed/customer_service_eval_report.json`。

Agent 端到端评估会真实调用模型接口；如果外部接口超时，脚本会把失败 case 写入报告，便于后续复盘。

默认后端入口：

- 工作台：`http://127.0.0.1:8001/`
- 接口文档：`http://127.0.0.1:8001/docs`
- 健康检查：`http://127.0.0.1:8001/health`
- 工具规格：`http://127.0.0.1:8001/tool-specs`
- 评估报告：`http://127.0.0.1:8001/eval-reports`
- Agent Run 详情页：`http://127.0.0.1:8001/agent-runs/{run_id}/view`

## 说明

本项目用于学习和作品集展示，重点在于智能客服 Agent 的工程化实现方式，包括 RAG 检索、工具调用、人工审核兜底、业务数据持久化、过程可观测和评估复盘闭环。
