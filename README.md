# 智能客服运营平台 Agent

更新时间：2026-07-29

这是一个用于作品集展示的 AI 客服 Agent 工程化项目。它不是简单聊天机器人，也不是只把 PDF 丢给大模型做问答，而是围绕真实客服系统常见链路实现了一套可运行、可观测、可评估、可解释的智能客服工作台。

核心链路：

```text
用户问题
  -> FastAPI /chat
  -> CustomerServiceAgent 生成 run_id
  -> 高风险规则前置识别
  -> LangChain Agent 决策是否调用工具
  -> Tools 查询知识库、订单、客户或创建工单
  -> RAG 使用 Milvus 检索政策依据
  -> SQLAlchemy/PostgreSQL 保存消息、工单、工具日志、引用来源和 Agent run
  -> 前端工作台展示聊天、工单、知识库和 Trace
```

这个项目的重点不是“模型回答得像不像人”，而是展示一个 AI Agent 项目从学习 Demo 到工程化作品的过程：有工具、有知识库、有数据库、有人工审核边界、有故障降级、有评估脚本、有前端展示。

---

## 当前功能

| 模块 | 已实现内容 |
|---|---|
| FastAPI 后端 | `/chat`、`/health`、`/workbench/state`、`/tickets/{ticket_id}/status`、`/agent-runs/{run_id}` |
| LangChain Agent | 使用 `create_agent` 编排模型和工具，按问题类型自主调用工具 |
| 业务工具 Tools | 知识库检索、订单查询、客户资料查询、创建工单 |
| RAG 知识库 | 支持 markdown、txt、json FAQ、PDF、扫描 PDF OCR 文本入库 |
| Milvus 向量检索 | 使用 SiliconFlow `BAAI/bge-m3` 生成 1024 维向量，Milvus 做相似度检索 |
| OCR | 扫描 PDF 离线 OCR 后进入 RAG 管线 |
| 数据库 | SQLAlchemy ORM + Alembic 迁移，支持 SQLite 或 PostgreSQL |
| 人工审核 | 投诉、赔偿、隐私、账号异常、法律等高风险问题进入 `pending_review` |
| Trace 可观测 | 每次请求有 `run_id`，可查询消息、工具调用、引用来源和最终状态 |
| 前端工作台 | 浏览器展示聊天、工单、知识库、Agent 调用过程和评估入口 |
| 评估脚本 | RAG eval 和 Agent eval，检查命中、工具调用、状态和引用来源 |

当前数据规模：

```text
data/knowledge_base/sources.json：23 条知识源
data/processed/documents.jsonl：23 条标准文档
data/processed/chunks.jsonl：48 个知识切块
data/processed/ocr_texts：4 份 OCR 文本
data/eval/rag_eval.json：24 条 RAG 评估用例
backend/app/data/eval/customer_service_eval.json：30 条 Agent 评估用例
```

---

## 技术栈

后端：

```text
Python
FastAPI
Pydantic
LangChain
DeepSeek Chat Model
SQLAlchemy
Alembic
PostgreSQL / SQLite
```

RAG：

```text
SiliconFlow Embedding
BAAI/bge-m3
Milvus
LangChain Text Splitter
pypdf
PaddleOCR
```

前端：

```text
HTML
CSS
JavaScript
FastAPI static files
```

---

## 项目结构

```text
backend/
  __init__.py
  app/
    main.py                         FastAPI 应用入口
    agents/
      customer_service_agent.py      Agent 主流程
    core/
      config.py                      .env 配置中心
    db/
      base.py                        SQLAlchemy Base
      models_sqlalchemy.py           ORM 表模型
      session_sqlalchemy.py          engine 和 SessionLocal
      session.py                     数据库业务访问函数
    evals/
      run_customer_service_eval.py   Agent 端到端评估
    rag/
      documents.py                   工作台读取已处理文档
      loaders.py                     加载 markdown/txt/json/pdf
      retriever.py                   Milvus 在线检索
    schemas/
      chat.py                        /chat 请求响应模型
    services/
      risk_service.py                高风险规则识别
    static/
      index.html                     工作台页面
      app.js                         工作台交互脚本
      styles.css                     工作台样式
    tools/
      knowledge_tools.py             RAG 工具
      order_tools.py                 订单工具
      customer_tools.py              客户工具
      ticket_tools.py                工单工具

scripts/
  ocr_documents.py                   扫描 PDF OCR
  prepare_documents.py               sources.json -> documents.jsonl
  build_chunks.py                    documents.jsonl -> chunks.jsonl
  ingest_knowledge_base.py           chunks -> Embedding -> Milvus
  run_rag_eval.py                    RAG 检索评估

data/
  knowledge_base/                    原始知识库资料
  processed/                         OCR、标准文档、切块、入库报告
  eval/                              RAG 评估集

migrations/
  env.py                             Alembic 迁移环境
  versions/                          数据库迁移脚本
```

---

## 模块演进说明

### 1. 后端入口：从脚本到 FastAPI 服务

最开始只是学习 LangChain 和工具调用，可以在 Python 脚本里直接调用 Agent。

后来为什么升级：

```text
作品集项目需要可展示、可调用、可联调。
如果只有命令行脚本，无法展示 API、前端工作台、健康检查、Trace 查询。
```

现在怎么改进：

```text
backend/app/main.py
```

实现了：

```text
POST /chat                         统一聊天入口
GET /health                        检查数据库和 Milvus
GET /workbench/state               前端工作台数据源
PATCH /tickets/{ticket_id}/status  工单状态流转
GET /agent-runs/{run_id}           查询一次 Agent 执行详情
GET /docs                          FastAPI 自动生成的 OpenAPI 文档
GET /                              前端工作台首页
```

### 2. Agent：从“直接问模型”到“模型决策 + 工具执行”

最开始可以只把用户问题发给模型，让模型直接回答。

后来为什么升级：

```text
客服场景里很多答案不能靠模型编：
订单状态要查订单系统；
客户资料要查客户系统；
退款政策要查知识库；
投诉、赔偿、隐私、法律问题要走人工审核。
```

现在怎么改进：

```text
backend/app/agents/customer_service_agent.py
```

Agent 使用 `create_agent`，挂载四个工具：

```text
search_knowledge_base    查询知识库
get_latest_order         查询最近订单
get_customer_info        查询客户资料
create_ticket            创建客服工单
```

一次 `/chat` 的核心处理：

```text
1. 生成 run_id
2. 读取最近几轮历史消息
3. 保存用户消息
4. 先用风险规则识别高风险问题
5. 高风险直接创建 pending_review 工单
6. 普通问题交给 LangChain Agent
7. 从 LangChain messages 中解析工具调用 Trace
8. 保存工具调用日志
9. 提取 RAG 引用来源
10. 推断业务状态 answered/no_answer/rag_unavailable/pending_review
11. 保存 assistant 回复和 Agent run
12. 返回 ChatResponse
```

### 3. Tools：从普通函数到 Agent 可调用工具

最开始工具可以只是普通 Python 函数，比如 `get_order(user_id)`。

后来为什么升级：

```text
Agent 要根据工具名、参数说明和 docstring 自主决定是否调用工具。
普通函数不能直接暴露给 LangChain Agent，需要用 @tool 包装。
```

现在怎么改进：

```text
backend/app/tools/knowledge_tools.py
backend/app/tools/order_tools.py
backend/app/tools/customer_tools.py
backend/app/tools/ticket_tools.py
```

工具都返回 JSON 字符串，因为：

```text
模型可以读懂；
后端可以解析；
工具日志可以保存；
前端可以展示；
评估脚本可以检查。
```

### 4. RAG：从内置文本到多来源知识库 + Milvus

最开始可以把几条政策写在代码里，或者用简单列表做关键词匹配。

后来为什么升级：

```text
真实客服知识库会有很多文件和格式：
markdown、txt、FAQ JSON、PDF、扫描 PDF。
如果知识直接写代码里，无法维护、无法扩展、无法评估。
```

现在怎么改进：

RAG 被拆成离线和在线两条路径。

离线路径：

```text
data/knowledge_base/sources.json
  -> scripts/ocr_documents.py
  -> scripts/prepare_documents.py
  -> scripts/build_chunks.py
  -> scripts/ingest_knowledge_base.py
  -> Milvus collection
```

在线路径：

```text
用户问题
  -> search_knowledge_base Tool
  -> backend/app/rag/retriever.py
  -> Embedding
  -> Milvus search
  -> MIN_RAG_SCORE 过滤
  -> 返回文档来源和内容片段
```

### 5. OCR：从跳过扫描 PDF 到离线识别

最开始扫描 PDF 不能被 `pypdf.extract_text()` 读取，只能暂时跳过。

后来为什么升级：

```text
客服真实资料经常有扫描件、截图版制度、盖章版 PDF。
如果扫描件不能入库，RAG 能力会明显不完整。
```

现在怎么改进：

```text
scripts/ocr_documents.py
```

流程：

```text
sources.json 中 need_ocr=true
  -> PaddleOCR 读取扫描 PDF
  -> 输出 data/processed/ocr_texts/{doc_id}.txt
  -> prepare_documents.py 把 OCR 文本当作普通文档继续处理
```

### 6. 数据库：从 SQLite 手写访问到 SQLAlchemy + Alembic

最开始用 SQLite 文件保存数据是合理的，简单、启动快、适合学习。

后来为什么升级：

```text
作品集展示需要说明真实项目如何迁移表结构。
手写 sqlite3 不利于切换 PostgreSQL，也不利于管理 CREATE TABLE / ALTER TABLE。
```

现在怎么改进：

```text
backend/app/db/models_sqlalchemy.py
backend/app/db/session_sqlalchemy.py
backend/app/db/session.py
migrations/
```

表结构包括：

```text
messages           保存用户消息和 AI 回复
message_sources    保存回答引用的知识库来源
tickets            保存客服工单和人工审核状态
tool_call_logs     保存工具调用参数、结果、错误和耗时
agent_runs         保存一次 /chat 请求的输入、输出、状态和时间
```

### 7. Trace：从内存 last_trace 到 run_id 持久化

最开始可以在 Agent 对象里保存 `last_trace`，调试时很方便。

后来为什么升级：

```text
last_trace 是内存变量，并发请求会互相覆盖。
服务重启后 trace 丢失。
评估脚本也不应该依赖某个对象的临时状态。
```

现在怎么改进：

```text
/chat 返回 run_id
agent_runs 保存主记录
tool_call_logs 保存工具调用
message_sources 保存引用来源
/agent-runs/{run_id} 查询完整执行过程
```

### 8. 高风险人工审核：从提示词约束到后端规则兜底

最开始只在系统提示词里要求模型遇到投诉、赔偿等问题创建工单。

后来为什么升级：

```text
提示词不是强规则，模型可能漏判。
客服高风险问题不能依赖模型“应该会做”。
```

现在怎么改进：

```text
backend/app/services/risk_service.py
```

规则集中管理：

```text
投诉、赔偿、律师、法律、起诉、隐私、泄露、举报、账号被盗、账号异常、人工处理
```

命中后：

```text
risk_level = high
status = pending_review
ticket.description 写入审核原因和命中关键词
tickets 表保存 risk_reason 和 matched_keyword
```

### 9. 前端：从 Swagger 测试到客服工作台

最开始用 `/docs` 调接口已经能验证后端功能。

后来为什么升级：

```text
面试展示时，只看 Swagger 不够直观。
需要一个页面同时看到聊天、工单、知识库和工具调用过程。
```

现在怎么改进：

```text
backend/app/static/index.html
backend/app/static/app.js
backend/app/static/styles.css
```

工作台展示：

```text
聊天窗口
Agent 调用过程
知识库列表
工单列表
评估入口
```

### 10. 评估：从人工点测到脚本化验证

最开始可以手动在 Swagger 里输入问题，看回答是否合理。

后来为什么升级：

```text
Agent 和 RAG 调整后容易出现回归。
比如阈值改了、chunk 改了、工具提示改了，都可能影响结果。
```

现在怎么改进：

```text
scripts/run_rag_eval.py
backend/app/evals/run_customer_service_eval.py
```

RAG eval 关注：

```text
top1_hit_rate
top3_hit_rate
no_answer_accuracy
avg_top_score
```

Agent eval 关注：

```text
工具是否调用正确
是否调用了禁止工具
RAG 来源是否命中
最终状态是否符合预期
是否应该回答
```

---

## 环境准备

### 1. 激活环境

```powershell
conda activate langchain1.2
```

如果 Windows 终端中文乱码：

```powershell
$env:PYTHONIOENCODING="utf-8"
```

### 2. 安装依赖

```powershell
pip install -r requirements.txt
```

### 3. 配置 `.env`

复制示例配置：

```powershell
Copy-Item .env.example .env
```

填写真实密钥，不要提交 `.env`。

关键配置：

```env
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com

SILICONFLOW_API_KEY=
SILICONFLOW_BASE_URL=https://api.siliconflow.cn/v1
SILICONFLOW_EMBED_MODEL=BAAI/bge-m3
SILICONFLOW_EMBED_DIM=1024

MILVUS_URI=http://localhost:19531
MILVUS_DB_NAME=customer_service_rag
MILVUS_COLLECTION_NAME=customer_service_docs
MILVUS_TIMEOUT_SECONDS=5

MIN_RAG_SCORE=0.60

DATABASE_URL=postgresql+psycopg2://customer_service:customer_service@localhost:5432/customer_service
DATABASE_CONNECT_TIMEOUT_SECONDS=5
```

说明：

```text
.env.example 默认保留 SQLite 配置，方便临时轻量运行。
作品集最终展示建议使用 PostgreSQL。
```

---

## 启动项目

### 1. 启动 PostgreSQL

确保 Docker Desktop 已启动。

```powershell
docker compose up -d postgres
```

检查：

```powershell
docker ps
Test-NetConnection -ComputerName localhost -Port 5432
```

### 2. 执行数据库迁移

```powershell
python -m alembic upgrade head
```

检查当前版本：

```powershell
python -m alembic current
```

预期 head：

```text
7b9c2d4a6f10
```

### 3. 启动 Milvus

当前项目没有把 Milvus 写进 `docker-compose.yml`，因为你本机使用的是外部 Milvus 容器。项目通过 `.env` 的 `MILVUS_URI` 连接它。

检查端口：

```powershell
Test-NetConnection -ComputerName localhost -Port 19531
```

如果端口不通，RAG 会降级，`/health` 会显示 `degraded`。

### 4. 构建知识库

如果数据没改过，可以直接入库。如果新增或修改了知识库，按下面顺序重新跑。

扫描 PDF OCR：

```powershell
python -m scripts.ocr_documents
```

普通文档预处理：

```powershell
python -m scripts.prepare_documents
```

文档切块：

```powershell
python -m scripts.build_chunks
```

写入 Milvus：

```powershell
python -m scripts.ingest_knowledge_base
```

RAG 评估：

```powershell
python -m scripts.run_rag_eval
```

### 5. 启动后端

```powershell
python -m uvicorn backend.app.main:app --reload
```

打开：

```text
Swagger: http://127.0.0.1:8000/docs
工作台:  http://127.0.0.1:8000/
健康检查: http://127.0.0.1:8000/health
```

---

## API 示例

### `/chat`

请求：

```powershell
curl -X POST `
  "http://127.0.0.1:8000/chat" `
  -H "Content-Type: application/json" `
  -d "{\"session_id\":\"demo_session\",\"user_id\":\"user-001\",\"message\":\"退款一般多久到账？\"}"
```

响应字段：

```json
{
  "run_id": "一次请求的唯一 ID",
  "session_id": "demo_session",
  "answer": "Agent 回复",
  "status": "answered",
  "sources": []
}
```

### `/agent-runs/{run_id}`

拿 `/chat` 返回的 `run_id` 查询：

```text
http://127.0.0.1:8000/agent-runs/{run_id}
```

可以看到：

```text
run          本次执行主记录
messages     用户消息和 AI 回复
tool_calls   调用了哪些工具、参数、结果、耗时、错误
sources      本次回答引用了哪些知识库文档
```

---

## 如何修改 RAG 数据集

### 1. 添加原始文件

按格式放到对应目录：

```text
markdown: data/knowledge_base/markdown/
txt:      data/knowledge_base/txt/
json FAQ: data/knowledge_base/json/
PDF:      data/knowledge_base/pdf/
扫描 PDF: data/knowledge_base/scanned/
```

### 2. 修改 `sources.json`

文件：

```text
data/knowledge_base/sources.json
```

新增一条：

```json
{
  "doc_id": "new_policy",
  "title": "新政策标题",
  "source_path": "data/knowledge_base/markdown/new_policy.md",
  "doc_type": "markdown",
  "business_area": "售后",
  "risk_level": "normal",
  "need_ocr": false
}
```

字段说明：

```text
doc_id         文档唯一 ID，评估和引用来源都会用它
title          前端展示标题
source_path    原始文件路径
doc_type       markdown / txt / json_faq / pdf / scanned_pdf
business_area  业务领域，例如售后、物流、财务、隐私、账号
risk_level     normal 或 high
need_ocr       扫描 PDF 填 true，普通文件填 false
```

### 3. 如果是扫描 PDF，先 OCR

```powershell
python -m scripts.ocr_documents
```

检查是否生成：

```text
data/processed/ocr_texts/{doc_id}.txt
```

### 4. 重新生成 RAG 数据

```powershell
python -m scripts.prepare_documents
python -m scripts.build_chunks
python -m scripts.ingest_knowledge_base
```

检查：

```text
data/processed/documents.jsonl
data/processed/chunks.jsonl
data/processed/ingest_report.json
```

### 5. 补充评估用例

文件：

```text
data/eval/rag_eval.json
```

新增问题，确认新文档能被检索到。

运行：

```powershell
python -m scripts.run_rag_eval
```

---

## 推荐展示路径

### 场景 1：退款政策问题

问题：

```text
退款审核通过后多久可以到账？
```

预期展示：

```text
Agent 调用 search_knowledge_base
RAG 命中 refund_policy
回答有知识库来源
tool_call_logs 和 message_sources 有记录
```

### 场景 2：订单物流问题

问题：

```text
我的订单到哪了？
```

预期展示：

```text
Agent 调用 get_latest_order
返回模拟订单状态和物流信息
Trace 面板展示订单工具调用
```

### 场景 3：客户资料问题

问题：

```text
我是 VIP 吗？
```

预期展示：

```text
Agent 调用 get_customer_info
返回 user-001 的 VIP 信息
```

### 场景 4：高风险人工审核

问题：

```text
我要投诉并要求赔偿，还要找律师。
```

预期展示：

```text
后端风险规则命中
创建 pending_review 工单
工单 description 包含进入人工审核原因和命中关键词
接口不直接承诺赔偿
```

### 场景 5：RAG 无答案

问题：

```text
你们能不能帮我查询股票账户？
```

预期展示：

```text
知识库没有明确依据
Agent 不编造答案
状态可能是 no_answer
```

### 场景 6：Milvus 故障降级

临时停止 Milvus 或改错 `MILVUS_URI` 后问政策问题。

预期展示：

```text
/chat 不应直接 500
search_knowledge_base 返回 unavailable=true
工具日志记录 rag_unavailable
回答说明知识库暂时不可用
```

---

## 常见排错

### `/health` 是 degraded

分别检查：

```powershell
docker ps
Test-NetConnection -ComputerName localhost -Port 5432
Test-NetConnection -ComputerName localhost -Port 19531
```

### 数据库表不存在

```powershell
python -m alembic upgrade head
```

### Milvus 报 `channel distribution is not serviceable`

这个通常不是代码语法问题，而是 Milvus collection 加载状态或 QueryNode 状态异常。

处理顺序：

```powershell
1. 确认 Milvus 容器正常运行
2. 重新执行 python -m scripts.ingest_knowledge_base
3. 重新测试 /health
4. 再测试 /chat
```

当前代码已经对这类 RAG 异常做了工具级降级，避免普通请求直接 500。

### RAG 命中不稳定

检查：

```text
MIN_RAG_SCORE 是否过高
chunk_size / chunk_overlap 是否适合当前文档
新增文档是否已经写入 sources.json
是否重新执行 ingest_knowledge_base
rag_eval.json 是否覆盖新问题
```

### Windows PowerShell 中文输出异常

```powershell
$env:PYTHONIOENCODING="utf-8"
```

---

## 面试讲法

可以这样开场：

```text
这个项目是一个 AI 客服 Agent 工程化作品。它不是单纯调用大模型聊天，
而是把客服系统里的知识库问答、订单查询、客户查询、工单创建、人工审核、
Trace 记录和评估脚本串成一个完整链路。

用户问题进入 FastAPI 后会生成 run_id。后端先做高风险规则识别，命中投诉、
赔偿、法律、隐私等关键词会直接创建 pending_review 工单。普通问题交给
LangChain Agent，由 Agent 决定调用知识库、订单、客户或工单工具。

RAG 侧我做了 sources 管理、多格式 loader、OCR、切块、Embedding、Milvus 入库和评估。
数据库侧从 SQLite 学习版升级到了 SQLAlchemy + Alembic，最终可以接 PostgreSQL。
每次执行都会保存 messages、tool_call_logs、message_sources 和 agent_runs，
所以可以通过 run_id 查到完整执行过程。
```

一句话总结：

```text
这个项目展示的是从“能跑的 Agent Demo”升级到“有工具、有 RAG、有数据库迁移、有人工审核、有 Trace 和故障降级的 AI Agent 工程化应用”。
```

---

## 后续可扩展方向

```text
1. 接入真实订单系统和客户系统
2. 增加登录、客服角色和权限控制
3. 扩大 RAG 与 Agent eval 数据集
4. 保存评估 JSON/HTML 报告
5. 接入 LangSmith 或 OpenTelemetry
6. 增加更多高风险规则和审核队列
7. 把 Milvus 纳入统一 docker-compose
8. 部署到云服务器并接入真实前端域名
```

当前项目已经足够作为作品集核心项目展示，后续重点应该是稳定演示、讲清架构、准备面试问题，而不是继续盲目堆功能。
