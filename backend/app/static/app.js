// 智能客服工作台前端脚本
// 这个文件负责调用 FastAPI 接口、保存浏览器端状态、渲染聊天/工单/知识库/Trace 面板，
// 并处理发送消息、刷新数据、修改工单状态等交互

// 页面状态对象：缓存后端返回的数据，避免每个渲染函数都重新请求接口
const state = {
  messages: [],
  tickets: [],
  toolCalls: [],
  documents: [],
  agentRuns: [],
  promptTemplates: [],
  evalReports: {},
  toolSpecs: [],
  health: null,
  activeView: "conversation",
  loading: false,
};

const CHAT_PREVIEW_LIMIT = 6;
const LIST_PREVIEW_LIMIT = 8;

// DOM 元素索引：集中保存页面节点，后续函数直接复用，减少重复 querySelector
const els = {
  apiStatus: document.querySelector("#apiStatus"),
  sessionId: document.querySelector("#sessionId"),
  userId: document.querySelector("#userId"),
  chatStream: document.querySelector("#chatStream"),
  traceList: document.querySelector("#traceList"),
  knowledgeList: document.querySelector("#knowledgeList"),
  ticketList: document.querySelector("#ticketList"),
  ticketCount: document.querySelector("#ticketCount"),
  chatCount: document.querySelector("#chatCount"),
  toolCount: document.querySelector("#toolCount"),
  docCount: document.querySelector("#docCount"),
  promptCount: document.querySelector("#promptCount"),
  promptList: document.querySelector("#promptList"),
  runSummary: document.querySelector("#runSummary"),
  metricRuns: document.querySelector("#metricRuns"),
  metricMessages: document.querySelector("#metricMessages"),
  metricPendingTickets: document.querySelector("#metricPendingTickets"),
  metricDocuments: document.querySelector("#metricDocuments"),
  metricRagTop3: document.querySelector("#metricRagTop3"),
  chatForm: document.querySelector("#chatForm"),
  messageInput: document.querySelector("#messageInput"),
  refreshButton: document.querySelector("#refreshButton"),
  newSessionButton: document.querySelector("#newSessionButton"),
  workspaceGrid: document.querySelector("#workspaceGrid"),
  evalCaseCount: document.querySelector("#evalCaseCount"),
  evalReportList: document.querySelector("#evalReportList"),
  toolSpecList: document.querySelector("#toolSpecList"),
  navButtons: document.querySelectorAll(".nav-button[data-view]"),
  toast: document.querySelector("#toast"),
};

// 工具名称映射：把后端工具函数名转换成更适合工作台阅读的中文名
const toolNames = {
  search_knowledge_base: "知识库检索",
  get_latest_order: "订单查询",
  create_ticket: "创建工单",
  get_customer_info: "客户资料",
};

// 状态名称映射：统一聊天状态和工单状态的展示文案
const statusNames = {
  open: "待处理",
  pending_review: "待审核",
  resolved: "已解决",
  closed: "已关闭",
  answered: "已回答",
  rag_unavailable: "知识库暂不可用",
  no_answer: "无明确答案",
  failed: "执行失败",
  validation_error: "参数错误",
  unavailable: "不可用",
  tool_error: "工具错误",
  parse_error: "解析错误",
};

// 文本兜底转换：避免 undefined/null 被直接渲染成异常内容
function escapeText(value) {
  return String(value ?? "");
}

// 时间格式化：把 ISO 时间压缩成工作台更容易扫描的中文本地时间
function formatTime(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

// 毫秒格式化：Trace 和详情页里用短格式展示耗时。
function formatMs(value) {
  if (value === null || value === undefined || value === "") return "-";
  return `${Number(value)}ms`;
}

// 百分比格式化：评估报告里的 0-1 浮点值转成工作台展示文案。
function formatPercent(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "-";
  return `${(Number(value) * 100).toFixed(1)}%`;
}

// 文本截断：长知识库片段和工单描述默认只展示摘要，完整内容保留在后端详情里
function truncateText(value, maxLength = 180) {
  const text = escapeText(value).replace(/\s+/g, " ").trim();
  return text.length > maxLength ? `${text.slice(0, maxLength)}...` : text;
}

// Toast 提示：用于发送成功、刷新成功、接口失败等轻量反馈
function showToast(message) {
  els.toast.textContent = message;
  els.toast.classList.add("show");
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => {
    els.toast.classList.remove("show");
  }, 2600);
}

// 空状态组件：当某个列表没有数据时渲染统一的占位提示
function createEmpty(text) {
  const node = document.createElement("div");
  node.className = "empty-state";
  node.textContent = text;
  return node;
}

// JSON 请求封装：统一设置请求头、解析 JSON，并把非 2xx 状态转换成异常
async function requestJson(url, options = {}) {
  const response = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `HTTP ${response.status}`);
  }

  return response.json();
}

// 检查后端健康状态：用于顶部 API 状态标识
async function checkHealth() {
  try {
    const health = await requestJson("/health");
    state.health = health;
    const databaseOk = health.database?.ok;
    const milvusOk = health.milvus?.ok;
    els.apiStatus.textContent = databaseOk && milvusOk ? "API / DB / RAG 在线" : "依赖降级";
    els.apiStatus.classList.toggle("muted", !(databaseOk && milvusOk));
  } catch (error) {
    state.health = null;
    els.apiStatus.textContent = "API 离线";
    els.apiStatus.classList.add("muted");
  }
}

// 加载工作台状态：一次请求拿到消息、工单、工具日志和知识库文档
async function loadState() {
  const data = await requestJson("/workbench/state");
  state.messages = data.messages || [];
  state.tickets = data.tickets || [];
  state.toolCalls = data.tool_calls || [];
  state.documents = data.documents || [];
  state.agentRuns = data.agent_runs || [];
  state.promptTemplates = data.prompt_templates || [];
  state.evalReports = data.eval_reports || {};
  state.toolSpecs = data.tool_specs || [];
  render();
}

// 总渲染入口：根据当前 state 依次刷新演示指标、聊天、Trace、知识库、工单和 Prompt 面板
function render() {
  renderMetrics();
  renderMessages();
  renderRunSummary();
  renderToolCalls();
  renderDocuments();
  renderTickets();
  renderPrompts();
  renderEvalReports();
  renderToolSpecs();
}

// 渲染首屏指标：让面试官不用翻接口也能看到项目具备数据、工单、RAG 和评估结果
function renderMetrics() {
  const pendingTickets = state.tickets.filter((ticket) => ticket.status === "pending_review");
  els.metricRuns.textContent = String(state.agentRuns.length);
  els.metricMessages.textContent = String(state.messages.length);
  els.metricPendingTickets.textContent = String(pendingTickets.length);
  els.metricDocuments.textContent = String(state.documents.length);
  const top3 = state.evalReports?.rag?.summary?.top3_hit_rate;
  els.metricRagTop3.textContent = top3 === undefined ? "-" : formatPercent(top3);
}

// 渲染聊天消息：按 session_id 过滤，让同一个工作台能切换不同会话
function renderMessages() {
  const sessionId = els.sessionId.value.trim();
  const messages = state.messages.filter((message) => {
    return !sessionId || message.session_id === sessionId;
  });
  const visibleMessages = messages.slice(-CHAT_PREVIEW_LIMIT);

  els.chatStream.replaceChildren();
  els.chatCount.textContent = String(messages.length);

  if (!messages.length) {
    els.chatStream.appendChild(createEmpty("当前会话暂无消息"));
    return;
  }

  if (messages.length > visibleMessages.length) {
    const note = document.createElement("div");
    note.className = "history-note";
    note.textContent = `已隐藏 ${messages.length - visibleMessages.length} 条更早消息，仅展示最近 ${visibleMessages.length} 条。`;
    els.chatStream.appendChild(note);
  }

  for (const message of visibleMessages) {
    const item = document.createElement("article");
    item.className = `message ${message.role === "user" ? "user" : "assistant"}`;

    const meta = document.createElement("div");
    meta.className = "message-meta";

    const role = document.createElement("span");
    role.textContent = message.role === "user" ? "用户" : "Agent";

    const time = document.createElement("span");
    time.textContent = formatTime(message.created_at);

    const content = document.createElement("div");
    content.className = "message-content";
    content.textContent = escapeText(message.content);

    meta.append(role, time);
    item.append(meta, content);
    els.chatStream.appendChild(item);
  }

  els.chatStream.scrollTop = els.chatStream.scrollHeight;
}

// 渲染最近一次 Agent run：集中展示输入、状态、工具数量和 RAG 来源，是面试演示的讲解锚点
function renderRunSummary() {
  const sessionId = els.sessionId.value.trim();
  const runs = state.agentRuns.filter((run) => !sessionId || run.session_id === sessionId);
  els.runSummary.replaceChildren();

  if (!runs.length) {
    els.runSummary.appendChild(createEmpty("发送一个演示问题后，这里会显示最近一次 Agent run"));
    return;
  }

  const latest = runs[0];
  const calls = state.toolCalls.filter((call) => call.run_id === latest.run_id);
  const sources = extractSourcesFromToolCalls(calls);

  const card = document.createElement("article");
  card.className = "run-card";

  const row = document.createElement("div");
  row.className = "item-row";

  const title = document.createElement("div");
  title.className = "item-title";
  title.textContent = "最近一次执行";

  const status = document.createElement("span");
  status.className = `status-chip ${latest.status}`;
  status.textContent = statusNames[latest.status] || latest.status;

  const input = document.createElement("p");
  input.className = "item-body";
  input.textContent = latest.input || "";

  const meta = document.createElement("p");
  meta.className = "item-subtitle";
  meta.textContent = [
    `run_id: ${latest.run_id}`,
    `工具调用 ${latest.tool_count ?? calls.length} 次`,
    `耗时 ${formatMs(latest.duration_ms)}`,
    latest.failure_type ? `复盘类型 ${latest.failure_type}` : "",
    formatTime(latest.started_at),
  ].filter(Boolean).join(" · ");

  const link = document.createElement("a");
  link.className = "run-link";
  link.href = `/agent-runs/${encodeURIComponent(latest.run_id)}/view`;
  link.target = "_blank";
  link.rel = "noreferrer";
  link.textContent = "查看完整 Trace 详情";

  row.append(title, status);
  card.append(row, input, meta, link);

  if (sources.length) {
    const sourceWrap = document.createElement("div");
    sourceWrap.className = "source-list";
    for (const source of sources.slice(0, 3)) {
      const chip = document.createElement("span");
      chip.className = "source-chip";
      chip.textContent = `${source.doc_id} · ${Number(source.score || 0).toFixed(3)}`;
      sourceWrap.appendChild(chip);
    }
    card.appendChild(sourceWrap);
  }

  els.runSummary.appendChild(card);
}

// 渲染工具调用 Trace：展示 Agent 调用了什么工具、传了什么参数、拿到了什么结果
function renderToolCalls() {
  const sessionId = els.sessionId.value.trim();
  const runs = state.agentRuns.filter((run) => !sessionId || run.session_id === sessionId);
  const latestRunId = runs[0]?.run_id;
  const calls = state.toolCalls
    .filter((call) => latestRunId ? call.run_id === latestRunId : (!sessionId || call.session_id === sessionId))
    .slice(0, LIST_PREVIEW_LIMIT);

  els.toolCount.textContent = String(calls.length);
  els.traceList.replaceChildren();

  if (!calls.length) {
    els.traceList.appendChild(createEmpty("暂无工具调用；发送演示问题后，这里只显示最近一次执行链路"));
    return;
  }

  for (const call of calls) {
    const item = document.createElement("article");
    item.className = "trace-item";

    const row = document.createElement("div");
    row.className = "item-row";

    const title = document.createElement("div");
    title.className = "item-title";
    title.textContent = toolNames[call.tool_name] || call.tool_name;

    const time = document.createElement("span");
    time.className = "source-chip";
    time.textContent = `${statusNames[call.status] || call.status || "success"} · ${formatMs(call.duration_ms)}`;

    const args = document.createElement("p");
    args.className = "item-body";
    args.textContent = compactJson(call.arguments);

    const result = document.createElement("p");
    result.className = "item-subtitle";
    result.textContent = summarizeToolResult(call);

    row.append(title, time);
    item.append(row, args, result);
    els.traceList.appendChild(item);
  }
}

// 渲染最近一次评估报告：展示 RAG 和 Agent eval 的报告化结果。
function renderEvalReports() {
  const ragReport = state.evalReports?.rag || {};
  const agentReport = state.evalReports?.agent || {};
  els.evalCaseCount.textContent = `RAG ${ragReport.case_count || 0} cases`;
  els.evalReportList.replaceChildren();

  els.evalReportList.append(
    createEvalReportCard("RAG 检索评估", ragReport, [
      ["通过率", formatPercent(ragReport.summary?.pass_rate)],
      ["Top1", formatPercent(ragReport.summary?.top1_hit_rate)],
      ["Top3", formatPercent(ragReport.summary?.top3_hit_rate)],
      ["无答案准确率", formatPercent(ragReport.summary?.no_answer_accuracy)],
    ]),
    createEvalReportCard("Agent 端到端评估", agentReport, [
      ["通过率", formatPercent(agentReport.summary?.pass_rate)],
      ["通过", `${agentReport.summary?.passed ?? "-"} / ${agentReport.summary?.total ?? "-"}`],
      ["失败", String(agentReport.summary?.failed ?? "-")],
      ["状态数", formatStatusCounts(agentReport.summary?.status_counts)],
    ]),
  );
}

// 评估报告卡片：报告未运行时也显示明确状态，方便面试前检查。
function createEvalReportCard(titleText, report, metrics) {
  const card = document.createElement("article");
  card.className = "eval-card";

  const row = document.createElement("div");
  row.className = "item-row";

  const title = document.createElement("p");
  title.className = "item-title";
  title.textContent = titleText;

  const status = document.createElement("span");
  status.className = "source-chip";
  status.textContent = report.status === "ready" ? "ready" : report.status || "not_run";

  const meta = document.createElement("p");
  meta.className = "item-subtitle";
  meta.textContent = report.generated_at
    ? `${formatTime(report.generated_at)} · ${report.report_file || ""}`
    : `尚未生成报告 · ${report.report_file || ""}`;

  const metricGrid = document.createElement("div");
  metricGrid.className = "eval-metrics";
  for (const [label, value] of metrics) {
    const item = document.createElement("div");
    const labelNode = document.createElement("span");
    labelNode.textContent = label;
    const valueNode = document.createElement("strong");
    valueNode.textContent = value;
    item.append(labelNode, valueNode);
    metricGrid.appendChild(item);
  }

  row.append(title, status);
  card.append(row, meta, metricGrid);
  return card;
}

// 把 Agent eval 的状态分布压缩成一行展示。
function formatStatusCounts(counts) {
  if (!counts || typeof counts !== "object") return "-";
  return Object.entries(counts)
    .map(([status, count]) => `${status}:${count}`)
    .join(" ");
}

// 渲染 Tool Calling 规格：展示每个业务工具的入参、出参和错误码。
function renderToolSpecs() {
  els.toolSpecList.replaceChildren();

  if (!state.toolSpecs.length) {
    els.toolSpecList.appendChild(createEmpty("暂无工具规格"));
    return;
  }

  const card = document.createElement("article");
  card.className = "eval-card";

  const title = document.createElement("p");
  title.className = "item-title";
  title.textContent = "Tool Calling 协议";

  const body = document.createElement("div");
  body.className = "tool-spec-grid";

  for (const spec of state.toolSpecs) {
    const item = document.createElement("details");
    item.className = "tool-spec-item";

    const summary = document.createElement("summary");
    summary.textContent = `${spec.title} · ${spec.name}`;

    const desc = document.createElement("p");
    desc.className = "item-subtitle";
    desc.textContent = spec.description;

    const io = document.createElement("p");
    io.className = "item-body";
    const inputs = (spec.inputs || []).map((input) => `${input.name}${input.required ? "*" : ""}`).join(", ");
    io.textContent = `入参：${inputs || "-"}；错误码：${(spec.error_codes || []).join(", ") || "-"}`;

    item.append(summary, desc, io);
    body.appendChild(item);
  }

  card.append(title, body);
  els.toolSpecList.appendChild(card);
}

// 从工具调用结果中提取 RAG 来源，用于最近一次 run 的首屏展示
function extractSourcesFromToolCalls(calls) {
  const seen = new Set();
  const sources = [];

  for (const call of calls) {
    if (call.tool_name !== "search_knowledge_base") continue;
    const docs = call.result?.results || [];
    for (const doc of docs) {
      if (!doc.doc_id || seen.has(doc.doc_id)) continue;
      seen.add(doc.doc_id);
      sources.push(doc);
    }
  }

  return sources;
}

// 渲染知识库列表：展示当前已处理文档，方便确认 RAG 数据集是否更新成功
function renderDocuments() {
  els.docCount.textContent = String(state.documents.length);
  els.knowledgeList.replaceChildren();

  if (!state.documents.length) {
    els.knowledgeList.appendChild(createEmpty("暂无知识库文档"));
    return;
  }

  for (const doc of state.documents.slice(0, state.activeView === "knowledge" ? state.documents.length : LIST_PREVIEW_LIMIT)) {
    const item = document.createElement("article");
    item.className = "doc-item";

    const row = document.createElement("div");
    row.className = "item-row";

    const title = document.createElement("div");
    title.className = "item-title";
    title.textContent = doc.title;

    const source = document.createElement("span");
    source.className = "source-chip";
    source.textContent = doc.doc_id;

    const content = document.createElement("p");
    content.className = "item-body";
    content.textContent = truncateText(doc.content, 220);

    const meta = document.createElement("p");
    meta.className = "item-subtitle";
    const metadata = doc.metadata || {};
    meta.textContent = [
      metadata.source_kind ? `来源类型：${metadata.source_kind}` : "",
      metadata.jurisdiction ? `地区：${metadata.jurisdiction}` : "",
      metadata.business_area ? `业务：${metadata.business_area}` : "",
      metadata.risk_level ? `风险：${metadata.risk_level}` : "",
      doc.doc_type ? `类型：${doc.doc_type}` : "",
    ].filter(Boolean).join("；");

    row.append(title, source);
    item.append(row);
    if (meta.textContent) {
      item.appendChild(meta);
    }
    item.appendChild(content);
    els.knowledgeList.appendChild(item);
  }
}

// 渲染 Prompt 模板：展示角色、工具路由、RAG 边界和高风险转人工等提示词工程设计
function renderPrompts() {
  els.promptCount.textContent = String(state.promptTemplates.length);
  els.promptList.replaceChildren();

  if (!state.promptTemplates.length) {
    els.promptList.appendChild(createEmpty("暂无 Prompt 模板"));
    return;
  }

  state.promptTemplates.forEach((prompt, index) => {
    const item = document.createElement("details");
    item.className = "prompt-item";
    item.open = index === 0;

    const row = document.createElement("summary");
    row.className = "item-row";

    const title = document.createElement("div");
    title.className = "item-title";
    title.textContent = prompt.title;

    const name = document.createElement("span");
    name.className = "source-chip";
    name.textContent = prompt.name;

    const goal = document.createElement("p");
    goal.className = "item-body";
    goal.textContent = prompt.goal;

    const when = document.createElement("p");
    when.className = "item-subtitle";
    when.textContent = `使用场景：${prompt.when_to_use}`;

    const template = document.createElement("pre");
    template.className = "prompt-template";
    template.textContent = prompt.template;

    row.append(title, name);
    item.append(row, goal, when, template);
    els.promptList.appendChild(item);
  });
}

// 渲染工单列表：展示工单状态、风险原因，并提供状态更新按钮
function renderTickets() {
  const sessionId = els.sessionId.value.trim();
  const sessionTickets = state.tickets.filter((ticket) => !sessionId || ticket.session_id === sessionId);
  const tickets = (state.activeView === "tickets" ? state.tickets : sessionTickets)
    .slice(0, state.activeView === "tickets" ? 16 : LIST_PREVIEW_LIMIT);

  els.ticketCount.textContent = String(state.activeView === "tickets" ? state.tickets.length : sessionTickets.length);
  els.ticketList.replaceChildren();

  if (!tickets.length) {
    els.ticketList.appendChild(createEmpty("当前范围暂无工单"));
    return;
  }

  for (const ticket of tickets) {
    const item = document.createElement("article");
    item.className = "ticket-item";

    const row = document.createElement("div");
    row.className = "item-row";

    const titleWrap = document.createElement("div");
    const title = document.createElement("div");
    title.className = "item-title";
    title.textContent = ticket.title;

    const subtitle = document.createElement("p");
    subtitle.className = "item-subtitle";
    subtitle.textContent = `${ticket.ticket_id} · ${ticket.user_id} · ${formatTime(ticket.created_at)}`;

    const status = document.createElement("span");
    status.className = `status-chip ${ticket.status}`;
    status.textContent = statusNames[ticket.status] || ticket.status;

    const body = document.createElement("p");
    body.className = "item-body";
    body.textContent = truncateText(ticket.description, 180);

    const riskMeta = document.createElement("p");
    riskMeta.className = "item-subtitle";
    if (ticket.risk_reason || ticket.matched_keyword) {
      riskMeta.textContent = `审核原因：${ticket.risk_reason || "-"}；命中关键词：${ticket.matched_keyword || "-"}`;
    }

    const sourceMeta = document.createElement("p");
    sourceMeta.className = "item-subtitle";
    if (ticket.source_dataset || ticket.category || ticket.queue || ticket.language) {
      const parts = [
        ticket.source_dataset ? `来源：${ticket.source_dataset}` : "",
        ticket.category ? `分类：${ticket.category}` : "",
        ticket.queue ? `队列：${ticket.queue}` : "",
        ticket.language ? `语言：${ticket.language}` : "",
      ].filter(Boolean);
      sourceMeta.textContent = parts.join("；");
    }

    const actions = document.createElement("div");
    actions.className = "ticket-actions";
    actions.append(
      createTicketButton(ticket.ticket_id, "pending_review", "待审核"),
      createTicketButton(ticket.ticket_id, "resolved", "解决"),
      createTicketButton(ticket.ticket_id, "closed", "关闭"),
    );

    titleWrap.append(title, subtitle);
    row.append(titleWrap, status);
    item.append(row, body);
    if (riskMeta.textContent) {
      item.appendChild(riskMeta);
    }
    if (sourceMeta.textContent) {
      item.appendChild(sourceMeta);
    }
    item.appendChild(actions);
    els.ticketList.appendChild(item);
  }
}

// 创建工单状态按钮：点击后调用 PATCH /tickets/{ticket_id}/status
function createTicketButton(ticketId, status, label) {
  const button = document.createElement("button");
  button.type = "button";
  button.textContent = label;
  button.addEventListener("click", async () => {
    try {
      await requestJson(`/tickets/${encodeURIComponent(ticketId)}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      });
      showToast("工单状态已更新");
      await loadState();
    } catch (error) {
      showToast("工单状态更新失败");
    }
  });
  return button;
}

// 压缩 JSON 展示：避免工具参数太长撑开 Trace 卡片
function compactJson(value) {
  if (!value || typeof value !== "object") return "";
  const text = JSON.stringify(value, null, 0);
  return text.length > 120 ? `${text.slice(0, 120)}...` : text;
}

// 汇总工具结果：把不同工具的 JSON 返回值转成一句可读摘要
function summarizeToolResult(call) {
  const result = call.result || {};

  if (call.tool_name === "search_knowledge_base") {
    const docs = result.results || [];
    if (result.unavailable) return result.message || "知识库暂时不可用";
    if (!docs.length) return "未命中知识库";
    return `命中 ${docs.length} 条，首条来源 ${docs[0].doc_id}`;
  }

  if (call.tool_name === "create_ticket") {
    const ticket = result.ticket || {};
    return `工单 ${ticket.ticket_id || ""} · ${statusNames[ticket.status] || ticket.status || ""}`;
  }

  if (call.tool_name === "get_latest_order") {
    const order = result.order || {};
    return result.found ? `订单 ${order.order_id || ""} · ${order.status || ""}` : result.message || "";
  }

  if (call.tool_name === "get_customer_info") {
    const customer = result.customer || {};
    return result.found ? `${customer.name || ""} · ${customer.level || ""}` : result.message || "";
  }

  return compactJson(result);
}

// 发送聊天消息：调用 /chat 后重新加载工作台状态，让消息、工具日志、工单同步刷新
async function sendMessage(question) {
  const message = question ?? els.messageInput.value.trim();
  if (!message || state.loading) return;

  state.loading = true;
  const submitButton = els.chatForm.querySelector("button[type='submit']");
  submitButton.disabled = true;
  submitButton.querySelector("span").textContent = "处理中";

  try {
    await requestJson("/chat", {
      method: "POST",
      body: JSON.stringify({
        session_id: els.sessionId.value.trim() || "demo_session",
        user_id: els.userId.value.trim() || "user-001",
        message,
      }),
    });

    els.messageInput.value = "";
    await loadState();
    showToast("会话已更新");
  } catch (error) {
    showToast("请求失败，请查看终端日志");
  } finally {
    state.loading = false;
    submitButton.disabled = false;
    submitButton.querySelector("span").textContent = "发送";
  }
}

// 聊天表单提交事件：阻止页面刷新，并交给 sendMessage 调接口
els.chatForm.addEventListener("submit", (event) => {
  event.preventDefault();
  sendMessage();
});

// 刷新按钮事件：重新读取后端工作台状态。
els.refreshButton.addEventListener("click", async () => {
  await loadState();
  showToast("数据已刷新");
});

// 新会话按钮：不删除数据库历史，只切换到一个干净 session，方便面试前重新演示。
els.newSessionButton.addEventListener("click", () => {
  const stamp = new Date()
    .toISOString()
    .replace(/[-:TZ.]/g, "")
    .slice(0, 14);
  els.sessionId.value = `demo_${stamp}`;
  els.userId.value = "user-001";
  els.messageInput.value = "";
  render();
  setView("conversation");
  showToast("已切换到新演示会话");
});

// 会话和用户输入事件：切换筛选条件时直接重新渲染当前缓存数据
els.sessionId.addEventListener("input", render);
els.userId.addEventListener("input", render);

// 快捷问题事件：把示例问题填入输入框并切换到会话视图。
document.querySelectorAll("[data-question]").forEach((button) => {
  button.addEventListener("click", () => {
    els.messageInput.value = button.dataset.question;
    els.messageInput.focus();
    setView("conversation");
    showToast("演示问题已填入，点击发送即可运行");
  });
});

// 侧边栏导航事件：根据 data-view 切换当前工作台布局
els.navButtons.forEach((button) => {
  button.addEventListener("click", () => {
    setView(button.dataset.view);
  });
});

// 切换视图：通过 data-view 控制 CSS 布局，同时更新导航按钮选中态
function setView(view) {
  state.activeView = view;
  els.workspaceGrid.dataset.view = view;

  els.navButtons.forEach((button) => {
    const isActive = button.dataset.view === view;
    button.classList.toggle("active", isActive);
    button.setAttribute("aria-current", isActive ? "page" : "false");
  });

  render();
}

// 页面初始化：先检查 API，再加载工作台数据
checkHealth();
loadState().catch(() => {
  showToast("工作台数据加载失败");
});
