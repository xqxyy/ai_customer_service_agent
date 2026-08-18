// Agent Run 详情页脚本：按 run_id 读取 JSON Trace，并渲染成人能快速复盘的时间线。

const toolLabels = {
  search_knowledge_base: "知识库检索",
  get_latest_order: "订单查询",
  create_ticket: "创建工单",
  get_customer_info: "客户资料",
};

const statusLabels = {
  answered: "已回答",
  pending_review: "待人工审核",
  no_answer: "无明确答案",
  rag_unavailable: "知识库不可用",
  failed: "执行失败",
  hit: "命中",
  not_found: "未找到",
  validation_error: "参数错误",
  unavailable: "不可用",
  tool_error: "工具错误",
  parse_error: "解析错误",
};

const els = {
  jsonLink: document.querySelector("#jsonLink"),
  runSummary: document.querySelector("#runSummaryDetail"),
  messages: document.querySelector("#messageTimeline"),
  tools: document.querySelector("#toolTimeline"),
  sources: document.querySelector("#sourceTimeline"),
};

function getRunId() {
  const parts = window.location.pathname.split("/").filter(Boolean);
  return decodeURIComponent(parts[1] || "");
}

function formatTime(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function formatMs(value) {
  if (value === null || value === undefined || value === "") return "-";
  return `${Number(value)}ms`;
}

function compactJson(value) {
  return JSON.stringify(value ?? {}, null, 2);
}

function createEmpty(text) {
  const empty = document.createElement("div");
  empty.className = "empty-state";
  empty.textContent = text;
  return empty;
}

function createChip(text) {
  const chip = document.createElement("span");
  chip.className = "source-chip";
  chip.textContent = text;
  return chip;
}

function renderSummary(run, toolCalls, sources) {
  els.runSummary.replaceChildren();

  const metrics = [
    ["状态", statusLabels[run.status] || run.status || "-"],
    ["模型", [run.model_provider, run.model_name].filter(Boolean).join(" / ") || "-"],
    ["耗时", formatMs(run.duration_ms)],
    ["工具调用", String(run.tool_count ?? toolCalls.length)],
    ["RAG 命中", run.rag_hit === null || run.rag_hit === undefined ? "-" : run.rag_hit ? "是" : "否"],
    ["RAG 最高分", run.rag_top_score === null || run.rag_top_score === undefined ? "-" : Number(run.rag_top_score).toFixed(4)],
    ["创建工单", run.ticket_created ? "是" : "否"],
    ["复盘类型", run.failure_type || "-"],
  ];

  for (const [label, value] of metrics) {
    const item = document.createElement("article");
    item.className = "metric-card";
    const labelNode = document.createElement("span");
    labelNode.textContent = label;
    const valueNode = document.createElement("strong");
    valueNode.textContent = value;
    item.append(labelNode, valueNode);
    els.runSummary.appendChild(item);
  }

  const meta = document.createElement("article");
  meta.className = "metric-card wide";
  const label = document.createElement("span");
  label.textContent = "run_id";
  const value = document.createElement("strong");
  value.textContent = run.run_id;
  meta.append(label, value, createChip(`${formatTime(run.started_at)} -> ${formatTime(run.ended_at)}`));
  els.runSummary.appendChild(meta);

  if (run.error) {
    const error = document.createElement("article");
    error.className = "metric-card wide error";
    const title = document.createElement("span");
    title.textContent = "错误";
    const body = document.createElement("strong");
    body.textContent = run.error;
    error.append(title, body);
    els.runSummary.appendChild(error);
  }
}

function renderMessages(messages) {
  els.messages.replaceChildren();

  if (!messages.length) {
    els.messages.appendChild(createEmpty("没有消息记录"));
    return;
  }

  for (const message of messages) {
    const item = document.createElement("article");
    item.className = `message ${message.role === "user" ? "user" : "assistant"}`;

    const meta = document.createElement("div");
    meta.className = "message-meta";
    meta.append(createChip(message.role === "user" ? "用户" : "Agent"), createChip(formatTime(message.created_at)));

    const content = document.createElement("div");
    content.className = "message-content";
    content.textContent = message.content || "";

    item.append(meta, content);
    els.messages.appendChild(item);
  }
}

function renderTools(toolCalls) {
  els.tools.replaceChildren();

  if (!toolCalls.length) {
    els.tools.appendChild(createEmpty("本次执行没有工具调用"));
    return;
  }

  toolCalls.forEach((call, index) => {
    const item = document.createElement("article");
    item.className = "trace-item";

    const row = document.createElement("div");
    row.className = "item-row";

    const title = document.createElement("div");
    title.className = "item-title";
    title.textContent = `${index + 1}. ${toolLabels[call.tool_name] || call.tool_name}`;

    const status = createChip(`${statusLabels[call.status] || call.status || "success"} · ${formatMs(call.duration_ms)}`);
    row.append(title, status);

    const meta = document.createElement("p");
    meta.className = "item-subtitle";
    meta.textContent = [call.error ? `错误：${call.error}` : "", formatTime(call.started_at)].filter(Boolean).join(" · ");

    const args = document.createElement("details");
    args.className = "trace-json";
    const argsSummary = document.createElement("summary");
    argsSummary.textContent = "入参";
    const argsPre = document.createElement("pre");
    argsPre.textContent = compactJson(call.arguments);
    args.append(argsSummary, argsPre);

    const result = document.createElement("details");
    result.className = "trace-json";
    result.open = true;
    const resultSummary = document.createElement("summary");
    resultSummary.textContent = "返回";
    const resultPre = document.createElement("pre");
    resultPre.textContent = compactJson(call.result);
    result.append(resultSummary, resultPre);

    item.append(row);
    if (meta.textContent) item.appendChild(meta);
    item.append(args, result);
    els.tools.appendChild(item);
  });
}

function renderSources(sources) {
  els.sources.replaceChildren();

  if (!sources.length) {
    els.sources.appendChild(createEmpty("本次回答没有引用 RAG 来源"));
    return;
  }

  for (const source of sources) {
    const item = document.createElement("article");
    item.className = "doc-item";

    const row = document.createElement("div");
    row.className = "item-row";
    const title = document.createElement("div");
    title.className = "item-title";
    title.textContent = source.title || source.doc_id;
    row.append(title, createChip(`${source.doc_id} · ${Number(source.score || 0).toFixed(4)}`));

    const meta = document.createElement("p");
    meta.className = "item-subtitle";
    meta.textContent = [source.source, source.source_path].filter(Boolean).join(" · ");

    item.append(row, meta);
    els.sources.appendChild(item);
  }
}

async function loadTrace() {
  const runId = getRunId();
  els.jsonLink.href = `/agent-runs/${encodeURIComponent(runId)}`;

  const response = await fetch(`/agent-runs/${encodeURIComponent(runId)}`);
  if (!response.ok) {
    els.runSummary.appendChild(createEmpty("没有找到该 Agent run"));
    return;
  }

  const data = await response.json();
  renderSummary(data.run, data.tool_calls || [], data.sources || []);
  renderMessages(data.messages || []);
  renderTools(data.tool_calls || []);
  renderSources(data.sources || []);
}

loadTrace().catch((error) => {
  els.runSummary.appendChild(createEmpty(`Trace 加载失败：${error.message}`));
});
