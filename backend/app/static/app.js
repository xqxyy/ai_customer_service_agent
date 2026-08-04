// 智能客服工作台前端脚本
// 这个文件负责调用 FastAPI 接口、保存浏览器端状态、渲染聊天/工单/知识库/Trace 面板，
// 并处理发送消息、刷新数据、修改工单状态等交互

// 页面状态对象：缓存后端返回的数据，避免每个渲染函数都重新请求接口
const state = {
  messages: [],
  tickets: [],
  toolCalls: [],
  documents: [],
  loading: false,
};

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
  toolCount: document.querySelector("#toolCount"),
  docCount: document.querySelector("#docCount"),
  chatForm: document.querySelector("#chatForm"),
  messageInput: document.querySelector("#messageInput"),
  refreshButton: document.querySelector("#refreshButton"),
  workspaceGrid: document.querySelector("#workspaceGrid"),
  navButtons: document.querySelectorAll("[data-view]"),
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
    await requestJson("/health");
    els.apiStatus.textContent = "API 在线";
    els.apiStatus.classList.remove("muted");
  } catch (error) {
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
  render();
}

// 总渲染入口：根据当前 state 依次刷新四个核心面板
function render() {
  renderMessages();
  renderToolCalls();
  renderDocuments();
  renderTickets();
}

// 渲染聊天消息：按 session_id 过滤，让同一个工作台能切换不同会话
function renderMessages() {
  const sessionId = els.sessionId.value.trim();
  const messages = state.messages.filter((message) => {
    return !sessionId || message.session_id === sessionId;
  });

  els.chatStream.replaceChildren();

  if (!messages.length) {
    els.chatStream.appendChild(createEmpty("当前会话暂无消息"));
    return;
  }

  for (const message of messages) {
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

// 渲染工具调用 Trace：展示 Agent 调用了什么工具、传了什么参数、拿到了什么结果
function renderToolCalls() {
  const sessionId = els.sessionId.value.trim();
  const calls = state.toolCalls.filter((call) => {
    return !sessionId || call.session_id === sessionId;
  });

  els.toolCount.textContent = String(calls.length);
  els.traceList.replaceChildren();

  if (!calls.length) {
    els.traceList.appendChild(createEmpty("暂无工具调用"));
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
    time.textContent = formatTime(call.created_at);

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

// 渲染知识库列表：展示当前已处理文档，方便确认 RAG 数据集是否更新成功
function renderDocuments() {
  els.docCount.textContent = String(state.documents.length);
  els.knowledgeList.replaceChildren();

  if (!state.documents.length) {
    els.knowledgeList.appendChild(createEmpty("暂无知识库文档"));
    return;
  }

  for (const doc of state.documents) {
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
    content.textContent = doc.content;

    row.append(title, source);
    item.append(row, content);
    els.knowledgeList.appendChild(item);
  }
}

// 渲染工单列表：展示工单状态、风险原因，并提供状态更新按钮
function renderTickets() {
  els.ticketCount.textContent = String(state.tickets.length);
  els.ticketList.replaceChildren();

  if (!state.tickets.length) {
    els.ticketList.appendChild(createEmpty("暂无工单"));
    return;
  }

  for (const ticket of state.tickets) {
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
    body.textContent = ticket.description;

    const riskMeta = document.createElement("p");
    riskMeta.className = "item-subtitle";
    if (ticket.risk_reason || ticket.matched_keyword) {
      riskMeta.textContent = `审核原因：${ticket.risk_reason || "-"}；命中关键词：${ticket.matched_keyword || "-"}`;
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

// 会话和用户输入事件：切换筛选条件时直接重新渲染当前缓存数据
els.sessionId.addEventListener("input", render);
els.userId.addEventListener("input", render);

// 快捷问题事件：把示例问题填入输入框并切换到会话视图。
document.querySelectorAll("[data-question]").forEach((button) => {
  button.addEventListener("click", () => {
    els.messageInput.value = button.dataset.question;
    els.messageInput.focus();
    setView("conversation");
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
  els.workspaceGrid.dataset.view = view;

  els.navButtons.forEach((button) => {
    const isActive = button.dataset.view === view;
    button.classList.toggle("active", isActive);
    button.setAttribute("aria-current", isActive ? "page" : "false");
  });
}

// 页面初始化：先检查 API，再加载工作台数据
checkHealth();
loadState().catch(() => {
  showToast("工作台数据加载失败");
});
