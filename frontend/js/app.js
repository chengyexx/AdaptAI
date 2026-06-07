/* ═══════════════════════════════════════════════════════════
   AdaptAI App — 前后端分离 SPA
   状态管理 · API 调用 · WebSocket · UI 渲染
   ═══════════════════════════════════════════════════════════ */

/* ── Config ─────────────────────────────────────────────── */
// 自动检测 API/WS 地址：同域部署则使用当前 host，否则回退到 localhost
const API_HOST = (() => {
  try {
    if (window.location.hostname && window.location.hostname !== "" && window.location.hostname !== "127.0.0.1") {
      return window.location.origin;
    }
  } catch (_) { /* ignore */ }
  return "http://127.0.0.1:8000";
})();
const API_BASE = API_HOST;
const WS_BASE = API_HOST.replace(/^http/, "ws");

/* ── Global State ───────────────────────────────────────── */
const State = {
  threadId: null,
  session: null,
  currentAgent: "",
  progress: 0,
  status: "",
  yamlContent: null,
  view: "landing", // "landing" | "workspace"
};

/* ═══════════════════════════════════════════════════════════
   LANDING PAGE
   ═══════════════════════════════════════════════════════════ */

// Mode tabs
document.querySelectorAll(".tab").forEach(tab => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
    tab.classList.add("active");
    const mode = tab.dataset.mode;
    document.getElementById("paste-area").style.display = mode === "paste" ? "block" : "none";
    document.getElementById("upload-area").style.display = mode === "upload" ? "block" : "none";
  });
});

// Char count
const textarea = document.getElementById("novel-text");
const charCount = document.getElementById("char-count");
textarea.addEventListener("input", () => {
  charCount.textContent = textarea.value.length;
});

// File upload
const fileInput = document.getElementById("file-input");
const uploadText = document.getElementById("upload-text");
fileInput.addEventListener("change", () => {
  const file = fileInput.files[0];
  if (file) {
    uploadText.textContent = file.name;
  }
});

// Submit
async function submitNovel() {
  const btn = document.getElementById("btn-submit");
  const errorEl = document.getElementById("submit-error");
  const mode = document.querySelector(".tab.active").dataset.mode;

  errorEl.style.display = "none";
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner" style="width:18px;height:18px;border-width:2px"></span> 处理中...';

  try {
    const formData = new FormData();
    if (mode === "paste") {
      const text = textarea.value.trim();
      if (!text) {
        showError("请输入小说文本");
        return;
      }
      formData.append("text", text);
    } else {
      const file = fileInput.files[0];
      if (!file) {
        showError("请选择文件");
        return;
      }
      formData.append("file", file);
    }

    const resp = await fetch(`${API_BASE}/api/sessions`, {
      method: "POST",
      body: formData,
    });

    if (!resp.ok) {
      const data = await resp.json().catch(() => ({}));
      throw new Error(data.detail || "创建会话失败");
    }

    const data = await resp.json();
    State.threadId = data.thread_id;
    State.view = "workspace";
    State.status = data.status;

    switchView("workspace");
    await initWorkspace();

  } catch (e) {
    showError(e.message);
  } finally {
    btn.disabled = false;
    btn.innerHTML = "开始转换 →";
  }
}

function showError(msg) {
  const el = document.getElementById("submit-error");
  el.textContent = msg;
  el.style.display = "block";
}

/* ═══════════════════════════════════════════════════════════
   VIEW SWITCHING
   ═══════════════════════════════════════════════════════════ */

function switchView(view) {
  const landing = document.getElementById("landing-view");
  const workspace = document.getElementById("workspace-view");

  if (view === "workspace") {
    landing.classList.add("view-hidden");
    workspace.classList.remove("view-hidden");
  } else {
    workspace.classList.add("view-hidden");
    landing.classList.remove("view-hidden");
    disconnectWS();
    resetWorkspace();
  }
  State.view = view;
}

function goHome() {
  if (confirm("确定返回首页？当前会话将断开连接。")) {
    switchView("landing");
  }
}

function resetWorkspace() {
  State.threadId = null;
  State.session = null;
  State.currentAgent = "";
  State.progress = 0;
  State.status = "";
  State.yamlContent = null;

  document.getElementById("progress-fill").style.width = "0%";
  document.getElementById("progress-percent").textContent = "0%";
  document.getElementById("status-badge").textContent = "等待启动";
  document.getElementById("status-badge").className = "status-badge";
  document.getElementById("btn-start").disabled = false;
  document.getElementById("result-panel").style.display = "none";
  document.getElementById("hitl-panel").style.display = "none";
  document.getElementById("terminal-body").innerHTML = `
    <div class="terminal-empty">
      <span>点击左侧「开始转换」启动 AI Pipeline</span>
    </div>`;

  resetAllSteps();
}

function resetAllSteps() {
  document.querySelectorAll(".step").forEach(step => {
    step.classList.remove("done", "active", "error");
  });
  const agents = ["scout_agent", "hitl", "map_agent", "validator"];
  agents.forEach((agent, i) => {
    const icon = document.getElementById("icon-" + agent);
    if (icon) icon.textContent = String(i + 1);
  });
}

/* ═══════════════════════════════════════════════════════════
   WORKSPACE INIT
   ═══════════════════════════════════════════════════════════ */

async function initWorkspace() {
  // Cold start: REST restore
  try {
    const resp = await fetch(`${API_BASE}/api/sessions/${State.threadId}`);
    if (resp.ok) {
      const data = await resp.json();
      State.session = data;
      State.status = data.status;
      renderPipelineUI(data.pipeline_state, data.status);

      // Restore logs if there were errors
      if (data.errors && data.errors.length > 0) {
        data.errors.forEach(e => {
          addLog("error", e.message || JSON.stringify(e));
        });
      }

      // Check if already completed
      if (data.status === "completed") {
        handleComplete(data);
      }

      // Check for pending HITL
      if (data.pending_hitl) {
        renderHITL(data.pending_hitl, data.artifacts);
      }
    }
  } catch (e) {
    addLog("error", "加载会话状态失败: " + e.message);
  }

  // Connect WebSocket
  connectWS(State.threadId);

  // Update button state
  updateStartButton();
}

/* ═══════════════════════════════════════════════════════════
   PIPELINE START
   ═══════════════════════════════════════════════════════════ */

async function startPipeline() {
  const btn = document.getElementById("btn-start");
  btn.disabled = true;
  btn.textContent = "启动中...";

  // Clear previous state
  document.getElementById("result-panel").style.display = "none";
  document.getElementById("hitl-panel").style.display = "none";
  document.getElementById("terminal-body").innerHTML = "";
  resetAllSteps();
  document.getElementById("progress-fill").style.width = "0%";
  document.getElementById("progress-percent").textContent = "0%";

  // Update status badge
  document.getElementById("status-badge").textContent = "启动中";
  document.getElementById("status-badge").className = "status-badge running";

  addLog("info", "正在提交 Pipeline 任务...");

  try {
    const resp = await fetch(`${API_BASE}/api/sessions/${State.threadId}/start`, {
      method: "POST",
    });

    if (!resp.ok) {
      const data = await resp.json().catch(() => ({}));
      throw new Error(data.detail || "启动失败");
    }

    const data = await resp.json();
    State.status = data.status;

    if (data.message === "Pipeline 已在运行中") {
      addLog("warn", "Pipeline 已在运行中，无需重复启动");
      // Try to restore current state
      await refreshSession();
      renderPipelineUI(State.session?.pipeline_state, State.session?.status);
      updateStartButton();
      return;
    }

    addLog("success", "Pipeline 已在后台启动，实时进度将通过 WebSocket 推送");
    addLog("info", "等待 LLM 响应...");

    // 后台执行模式 — 状态通过 WebSocket 推送，无需轮询
    // 按钮保持 disabled，等待 WebSocket 事件更新

    // 启动超时监控：60 秒无进度则提示
    _startProgressWatchdog();

  } catch (e) {
    addLog("error", "启动失败: " + e.message);
    btn.disabled = false;
    btn.textContent = "开始转换";
    document.getElementById("status-badge").textContent = "启动失败";
    document.getElementById("status-badge").className = "status-badge error";
  }
}

async function refreshSession() {
  try {
    const resp = await fetch(`${API_BASE}/api/sessions/${State.threadId}`);
    if (resp.ok) {
      State.session = await resp.json();
      State.status = State.session.status;
    }
  } catch (e) {
    console.error("Refresh session failed:", e);
  }
}

/* ── Progress Watchdog ──  */
let _watchdogTimer = null;
let _lastProgressTime = 0;

function _startProgressWatchdog() {
  _stopProgressWatchdog();
  _lastProgressTime = Date.now();

  _watchdogTimer = setInterval(() => {
    const elapsed = (Date.now() - _lastProgressTime) / 1000;
    const status = State.status;

    // 已完成/错误/暂停状态不触发看门狗
    if (status === "completed" || status === "error" || (status && status.includes("_hitl"))) {
      _stopProgressWatchdog();
      return;
    }

    // 60 秒无进度，提示用户
    if (elapsed > 60 && elapsed < 65) {
      addLog("warn", "LLM 响应较慢（已等待 60s），小说较长或 API 繁忙，请耐心等待...");
    }

    // 120 秒无进度，提示可能卡住
    if (elapsed > 120 && elapsed < 125) {
      addLog("warn", "已等待 2 分钟，如持续无响应请检查后端控制台日志或刷新重试");
    }
  }, 5000); // 每 5 秒检查一次
}

function _stopProgressWatchdog() {
  if (_watchdogTimer) {
    clearInterval(_watchdogTimer);
    _watchdogTimer = null;
  }
}

function _touchProgress() {
  _lastProgressTime = Date.now();
}

/* ═══════════════════════════════════════════════════════════
   PIPELINE UI RENDERING
   ═══════════════════════════════════════════════════════════ */

function renderPipelineUI(pipelineState, status) {
  // HTML steps: scout_agent(0) → hitl(1) → map_agent(2) → validator(3)
  const agents = ["scout_agent", "hitl", "map_agent", "validator"];
  // 映射 HappyPath 旧 agent 名到 SMR 步骤
  const agentStepMap = {
    "chapter_parser": "scout_agent",
    "character_agent": "hitl",
    "scene_agent": "map_agent",
    "script_agent": "map_agent",
    "scout_agent": "scout_agent",
    "hitl": "hitl",
    "map_agent": "map_agent",
    "validator": "validator",
  };
  const rawAgent = pipelineState?.current_agent || "";
  const currentAgent = agentStepMap[rawAgent] || rawAgent;
  const progress = pipelineState?.progress || 0;

  // Progress bar
  const fill = document.getElementById("progress-fill");
  if (fill) fill.style.width = (progress * 100) + "%";
  const ptext = document.getElementById("progress-percent");
  if (ptext) ptext.textContent = Math.round(progress * 100) + "%";

  // Status badge
  const badge = document.getElementById("status-badge");
  const statusMap = {
    "created": "等待启动",
    "parsing": "章节解析中",
    "parsed": "解析完成",
    "char_extracting": "角色识别中",
    "char_hitl": "等待审阅",
    "char_done": "角色完成",
    "scene_segmenting": "场景切分中",
    "scene_hitl": "等待审阅",
    "scene_done": "场景完成",
    "script_generating": "剧本生成中",
    "script_hitl": "等待审阅",
    "script_done": "剧本完成",
    "validating": "校验中",
    "completed": "已完成",
    "error": "错误",
    "paused": "已暂停",
  };
  badge.textContent = statusMap[status] || (status || "未知");

  // Status badge style
  badge.className = "status-badge";
  if (status === "completed") badge.classList.add("completed");
  else if (status === "error") badge.classList.add("error");
  else if (status && status.includes("_hitl")) badge.classList.add("paused");
  else if (status && status !== "created") badge.classList.add("running");

  // Pipeline steps
  agents.forEach((agent, i) => {
    const step = document.querySelector(`.step[data-agent="${agent}"]`);
    const icon = document.getElementById("icon-" + agent);
    if (!step || !icon) return;

    step.classList.remove("done", "active", "error");
    const idx = agents.indexOf(currentAgent);

    if (status === "completed") {
      step.classList.add("done");
      icon.textContent = "✓";
    } else if (status === "error" && i === idx) {
      step.classList.add("error");
      icon.textContent = "✗";
    } else if (i < idx) {
      step.classList.add("done");
      icon.textContent = "✓";
    } else if (i === idx) {
      step.classList.add("active");
      icon.textContent = "●";
    } else {
      icon.textContent = String(i + 1);
    }

    // HITL pause indicator
    if (status && status.includes("_hitl") && agent === currentAgent) {
      icon.textContent = "⏸";
      step.classList.add("active");
    }
  });

  State.currentAgent = currentAgent;
  State.progress = progress;
}

function updateStartButton() {
  const btn = document.getElementById("btn-start");
  if (!btn) return;

  const s = State.status;
  if (!s || s === "created" || s === "paused") {
    btn.disabled = false;
    btn.textContent = "开始转换";
  } else if (s === "completed") {
    btn.disabled = true;
    btn.textContent = "已完成";
  } else if (s === "error") {
    btn.disabled = false;
    btn.textContent = "重新转换";
  } else {
    btn.disabled = true;
    btn.textContent = "运行中...";
  }
}

/* ═══════════════════════════════════════════════════════════
   TERMINAL LOG
   ═══════════════════════════════════════════════════════════ */

function addLog(level, msg) {
  const body = document.getElementById("terminal-body");

  // Remove empty state if present
  const empty = body.querySelector(".terminal-empty");
  if (empty) empty.remove();

  // Create or get log container
  let logContainer = body.querySelector(".terminal-log");
  if (!logContainer) {
    logContainer = document.createElement("div");
    logContainer.className = "terminal-log";
    body.appendChild(logContainer);
  }

  const now = new Date();
  const time = now.toLocaleTimeString("zh-CN", { hour12: false });

  const line = document.createElement("div");
  line.className = "log-line";
  line.innerHTML = `
    <span class="log-time">${time}</span>
    <span class="log-level ${level}">${level.toUpperCase()}</span>
    <span class="log-msg">${escapeHtml(msg)}</span>
  `;

  logContainer.appendChild(line);

  // Auto-scroll
  body.scrollTop = body.scrollHeight;
}

/* ═══════════════════════════════════════════════════════════
   COMPLETION HANDLER
   ═══════════════════════════════════════════════════════════ */

function handleComplete(data) {
  addLog("success", "Pipeline 执行完成！");
  document.getElementById("btn-start").disabled = true;
  document.getElementById("btn-start").textContent = "已完成";
  document.getElementById("status-badge").textContent = "已完成";
  document.getElementById("status-badge").className = "status-badge completed";

  const yaml = data.artifacts?.script_yaml || data.result?.script_yaml;
  if (yaml) {
    State.yamlContent = yaml;
    document.getElementById("yaml-content").textContent = yaml;
    document.getElementById("result-panel").style.display = "block";
  }
}

function copyYAML() {
  if (!State.yamlContent) return;
  navigator.clipboard.writeText(State.yamlContent).then(() => {
    addLog("success", "已复制到剪贴板");
  }).catch(() => {
    addLog("error", "复制失败，请手动复制");
  });
}

function downloadYAML() {
  if (!State.yamlContent) return;
  const blob = new Blob([State.yamlContent], { type: "text/yaml" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "screenplay.yaml";
  a.click();
  URL.revokeObjectURL(url);
  addLog("success", "YAML 文件已下载");
}

/* ═══════════════════════════════════════════════════════════
   HITL EDITOR
   ═══════════════════════════════════════════════════════════ */

function renderHITL(hitlMsg, artifacts) {
  const panel = document.getElementById("hitl-panel");
  if (!panel) return;
  panel.style.display = "block";

  const agent = hitlMsg.agent || hitlMsg.node || "";
  const data = hitlMsg.data || {};
  const reason = hitlMsg.reason || "low_confidence";
  const confidence = hitlMsg.confidence || 0;

  // ── Scout HITL: 角色 + 地点审阅 ──
  if (agent === "scout_agent" && data.characters) {
    // 缓存原始数据供提交时合并
    _scoutHitlData = JSON.parse(JSON.stringify(data));
    let html = `
      <div class="hitl-header">
        <div class="hitl-icon">🔍</div>
        <div>
          <div class="hitl-title">Scout 检查点: 审阅角色与地点设定</div>
          <div class="hitl-reason">
            ${reason} &nbsp;(置信度 ${Math.round(confidence * 100)}%)
          </div>
        </div>
      </div>
      <p style="color:var(--text-secondary);font-size:var(--text-sm);margin-bottom:var(--space-3)">
        AI 已从小说中提取以下角色和地点。请检查正确性，特别是<strong>角色性格</strong>和<strong>角色定位</strong>。修改后将作为全局上下文用于后续所有场景生成。
      </p>`;

    // 角色列表
    html += '<h4 style="color:var(--text-secondary);font-size:var(--text-sm);margin-bottom:var(--space-2)">👥 角色表 (' + data.characters.length + ' 人)</h4>';
    data.characters.forEach((c, i) => {
      html += `
        <div class="edit-card">
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:var(--space-2)">
            <div>
              <label>姓名</label>
              <input value="${esc(c.name || '')}" data-scout-char="${i}" data-field="name">
            </div>
            <div>
              <label>别称 (逗号分隔)</label>
              <input value="${esc((c.aliases || []).join(', '))}" data-scout-char="${i}" data-field="aliases">
            </div>
            <div>
              <label>外貌</label>
              <input value="${esc((c.description || {}).physical || '')}" data-scout-char="${i}" data-field="physical">
            </div>
            <div>
              <label>性格 <span style="color:var(--warning);font-size:var(--text-xs)">(重点审阅)</span></label>
              <input value="${esc((c.description || {}).personality || '')}" data-scout-char="${i}" data-field="personality" style="border-color:var(--warning)">
            </div>
          </div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:var(--space-2);margin-top:var(--space-2)">
            <div>
              <label>角色定位 <span style="color:var(--warning);font-size:var(--text-xs)">(重点审阅)</span></label>
              <select data-scout-char="${i}" data-field="role" style="width:100%;padding:var(--space-2);background:var(--bg-secondary);border:1px solid var(--warning);border-radius:var(--radius-sm);color:var(--text-primary);font-size:var(--text-sm);min-height:40px">
                <option value="protagonist" ${(c.role || '') === 'protagonist' ? 'selected' : ''}>主角 (Protagonist)</option>
                <option value="antagonist" ${(c.role || '') === 'antagonist' ? 'selected' : ''}>反派 (Antagonist)</option>
                <option value="supporting" ${(c.role || '') === 'supporting' ? 'selected' : ''}>配角 (Supporting)</option>
                <option value="minor" ${(c.role || '') === 'minor' ? 'selected' : ''}>龙套 (Minor)</option>
                <option value="cameo" ${(c.role || '') === 'cameo' ? 'selected' : ''}>客串 (Cameo)</option>
              </select>
            </div>
            <div>
              <label>重要度 (1-10)</label>
              <input type="number" min="1" max="10" value="${c.importance || 5}" data-scout-char="${i}" data-field="importance">
            </div>
          </div>
        </div>`;
    });

    // 地点列表（简化）
    if (data.locations && data.locations.length > 0) {
      html += '<h4 style="color:var(--text-secondary);font-size:var(--text-sm);margin:var(--space-4) 0 var(--space-2)">📍 地点表 (' + data.locations.length + ' 处)</h4>';
      data.locations.forEach((loc, i) => {
        html += `
          <div class="edit-card">
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:var(--space-2)">
              <div>
                <label>地点名</label>
                <input value="${esc(loc.name || '')}" data-scout-loc="${i}" data-field="name">
              </div>
              <div>
                <label>类型</label>
                <select data-scout-loc="${i}" data-field="type" style="width:100%;padding:var(--space-2);background:var(--bg-secondary);border:1px solid var(--border-default);border-radius:var(--radius-sm);color:var(--text-primary);font-size:var(--text-sm);min-height:40px">
                  <option value="INT." ${loc.type === 'INT.' ? 'selected' : ''}>INT. (内景)</option>
                  <option value="EXT." ${loc.type === 'EXT.' ? 'selected' : ''}>EXT. (外景)</option>
                </select>
              </div>
            </div>
          </div>`;
      });
    }

    html += `
      <div class="hitl-actions">
        <button class="btn-confirm" id="btn-scout-confirm">确认设定，继续执行</button>
        <button class="btn-skip" id="btn-scout-skip">跳过审阅，直接继续</button>
      </div>`;
    panel.innerHTML = html;
    panel.scrollIntoView({ behavior: "smooth" });

    // 事件绑定（innerHTML 后重新绑定）
    document.getElementById("btn-scout-confirm").addEventListener("click", submitScoutHITL);
    document.getElementById("btn-scout-skip").addEventListener("click", skipScoutHITL);
    return;
  }

  // ── 旧 HITL 兼容 ──
  _legacyHitlData = JSON.parse(JSON.stringify(data));
  _legacyHitlAgent = agent;

  let html = `
    <div class="hitl-header">
      <div class="hitl-icon">✋</div>
      <div>
        <div class="hitl-title">需要你的审阅</div>
        <div class="hitl-reason">
          原因：${reason} &nbsp;(置信度 ${Math.round(confidence * 100)}%)
        </div>
      </div>
    </div>`;

  if (agent === "character_agent" && data.characters) {
    html += '<h4 style="color:var(--text-secondary);font-size:var(--text-sm);margin-bottom:var(--space-3)">角色列表</h4>';
    data.characters.forEach((c, i) => {
      html += `
        <div class="edit-card">
          <label>姓名 <input value="${esc(c.name || "")}" data-char="${i}" data-field="name"></label>
          <label>别称 <input value="${esc((c.aliases || []).join(", "))}" data-char="${i}" data-field="aliases"></label>
          <label>外貌 <input value="${esc((c.description || {}).physical || "")}" data-char="${i}" data-field="physical"></label>
          <label>性格 <input value="${esc((c.description || {}).personality || "")}" data-char="${i}" data-field="personality"></label>
        </div>`;
    });
  } else if (agent === "scene_agent" && data.scenes) {
    html += '<h4 style="color:var(--text-secondary);font-size:var(--text-sm);margin-bottom:var(--space-3)">场景列表</h4>';
    data.scenes.forEach((s, i) => {
      html += `
        <div class="edit-card">
          <label>地点 <input value="${esc((s.heading || {}).location || "")}" data-scene="${i}" data-field="location"></label>
          <label>时段 <input value="${esc((s.heading || {}).time_of_day || "")}" data-scene="${i}" data-field="time"></label>
          <label>氛围 <input value="${esc(s.mood || "")}" data-scene="${i}" data-field="mood"></label>
        </div>`;
    });
  }

  html += `
    <div class="hitl-actions">
      <button class="btn-confirm" onclick="submitHITL('${agent}')">确认并继续</button>
      <button class="btn-skip" onclick="skipHITL()">跳过</button>
    </div>`;

  panel.innerHTML = html;
  panel.scrollIntoView({ behavior: "smooth" });
}

// ── Scout HITL 提交 ─────────────────────────────────────

// 缓存原始的 Scout HITL 数据，供提交时合并使用
let _scoutHitlData = null;

async function submitScoutHITL() {
  const btn = document.getElementById("btn-scout-confirm");
  if (btn) { btn.disabled = true; btn.textContent = "提交中..."; }

  addLog("info", "提交 Scout HITL 审阅...");

  try {
    // 基于原始数据，合并用户编辑
    const original = _scoutHitlData || { characters: [] };
    const characters = JSON.parse(JSON.stringify(original.characters || []));

    // 收集用户编辑
    document.querySelectorAll("[data-scout-char]").forEach(el => {
      const i = parseInt(el.dataset.scoutChar);
      if (isNaN(i) || !characters[i]) return;
      const field = el.dataset.field;
      if (!field) return;

      if (field === "name" || field === "role" || field === "importance") {
        characters[i][field] = el.value;
      } else if (field === "aliases") {
        characters[i].aliases = el.value.split(",").map(s => s.trim()).filter(Boolean);
      } else if (field === "physical" || field === "personality") {
        if (!characters[i].description) characters[i].description = {};
        characters[i].description[field] = el.value;
      }
    });

    const resp = await fetch(`${API_BASE}/api/sessions/${State.threadId}/hitl/continue`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ characters }),
    });

    if (resp.ok) {
      document.getElementById("hitl-panel").style.display = "none";
      document.getElementById("btn-start").disabled = true;
      document.getElementById("btn-start").textContent = "运行中...";
      document.getElementById("status-badge").textContent = "继续执行中";
      document.getElementById("status-badge").className = "status-badge running";
      addLog("success", "设定已应用，Pipeline 继续执行");
      _scoutHitlData = null;
    } else {
      const err = await resp.json().catch(() => ({}));
      addLog("error", "提交失败: " + (err.detail || resp.statusText));
      if (btn) { btn.disabled = false; btn.textContent = "确认设定，继续执行"; }
    }
  } catch (e) {
    addLog("error", "提交异常: " + e.message);
    if (btn) { btn.disabled = false; btn.textContent = "确认设定，继续执行"; }
  }
}

async function skipScoutHITL() {
  addLog("warn", "跳过 Scout 审阅，直接继续");
  try {
    await fetch(`${API_BASE}/api/sessions/${State.threadId}/hitl/skip-continue`, { method: "POST" });
    document.getElementById("hitl-panel").style.display = "none";
    document.getElementById("btn-start").disabled = true;
    document.getElementById("btn-start").textContent = "运行中...";
    document.getElementById("status-badge").textContent = "继续执行中";
    document.getElementById("status-badge").className = "status-badge running";
  } catch (e) {
    addLog("error", "跳过失败: " + e.message);
  }
}

// 缓存旧 HITL 的原始数据，供 submitHITL 合并使用
let _legacyHitlData = null;
let _legacyHitlAgent = "";

async function submitHITL(agent) {
  addLog("info", "提交人工编辑...");

  try {
    const original = _legacyHitlData || {};
    let payload = {};

    if (agent === "character_agent" && original.characters) {
      // 深克隆原始角色列表，合并用户编辑
      const characters = JSON.parse(JSON.stringify(original.characters));
      document.querySelectorAll("[data-char]").forEach(el => {
        const i = parseInt(el.dataset.char);
        if (isNaN(i) || !characters[i]) return;
        const field = el.dataset.field;
        if (!field) return;
        if (field === "name" || field === "role" || field === "importance") {
          characters[i][field] = el.value;
        } else if (field === "aliases") {
          characters[i].aliases = el.value.split(",").map(s => s.trim()).filter(Boolean);
        } else if (field === "physical" || field === "personality") {
          if (!characters[i].description) characters[i].description = {};
          characters[i].description[field] = el.value;
        }
      });
      payload = { characters };
    } else if (agent === "scene_agent" && original.scenes) {
      const scenes = JSON.parse(JSON.stringify(original.scenes));
      document.querySelectorAll("[data-scene]").forEach(el => {
        const i = parseInt(el.dataset.scene);
        if (isNaN(i) || !scenes[i]) return;
        const field = el.dataset.field;
        if (field) scenes[i][field] = el.value;
      });
      payload = { scenes };
    }

    await fetch(`${API_BASE}/api/sessions/${State.threadId}/hitl/continue`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    document.getElementById("hitl-panel").style.display = "none";
    _legacyHitlData = null;
    _legacyHitlAgent = "";
    addLog("success", "编辑已提交，继续执行");

    // Pipeline 由后端通过 WebSocket 自动推送恢复，无需手动调用 /start
  } catch (e) {
    addLog("error", "提交编辑失败: " + e.message);
  }
}

async function skipHITL() {
  addLog("warn", "跳过人工编辑，继续执行");
  document.getElementById("hitl-panel").style.display = "none";
  _legacyHitlData = null;
  _legacyHitlAgent = "";

  const btn = document.getElementById("btn-start");
  btn.disabled = true;
  btn.textContent = "运行中...";
  await fetch(`${API_BASE}/api/sessions/${State.threadId}/hitl/skip-continue`, { method: "POST" });
}

/* ═══════════════════════════════════════════════════════════
   WEBSOCKET
   ═══════════════════════════════════════════════════════════ */

let ws = null;
let wsSeq = 0;
let reconnectTimer = null;
let reconnectDelay = 1000;
let reconnectCount = 0;
const MAX_RECONNECT = 10;

function connectWS(threadId) {
  disconnectWS();

  const url = `${WS_BASE}/ws/${threadId}`;
  ws = new WebSocket(url);

  ws.onopen = () => {
    console.log("[WS] Connected");
    reconnectDelay = 1000;
    reconnectCount = 0;
    addLog("info", "WebSocket 已连接");

    // Resync if reconnecting
    if (wsSeq > 0) {
      ws.send(JSON.stringify({
        type: "resync",
        thread_id: threadId,
        last_seq: wsSeq,
      }));
    }
  };

  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    wsSeq = msg.seq || wsSeq;

    switch (msg.type) {
      case "progress":
        handleProgress(msg);
        break;
      case "token_stream":
        handleTokenStream(msg);
        break;
      case "hitl_pause":
        handleHITLPause(msg);
        break;
      case "stage_complete":
        handleStageComplete(msg);
        break;
      case "error":
        handleError(msg);
        break;
      case "complete":
        handleWSComplete(msg);
        break;
      case "resync_complete":
        addLog("info", "状态已同步");
        renderPipelineUI(
          { current_agent: msg.current_agent, progress: msg.progress },
          State.status
        );
        break;
      case "log":
        addLog(msg.level || "info", msg.message);
        break;
    }
  };

  ws.onclose = () => {
    reconnectCount++;
    if (reconnectCount > MAX_RECONNECT) {
      console.log("[WS] Max reconnect attempts reached, giving up");
      addLog("error", "WebSocket 重连失败次数过多，请刷新页面");
      return;
    }
    console.log(`[WS] Disconnected, reconnecting in ${reconnectDelay}ms (attempt ${reconnectCount}/${MAX_RECONNECT})`);
    addLog("warn", `连接断开，${Math.round(reconnectDelay / 1000)}s 后重连 (${reconnectCount}/${MAX_RECONNECT})`);
    reconnectTimer = setTimeout(() => connectWS(threadId), reconnectDelay);
    reconnectDelay = Math.min(reconnectDelay * 2, 30000);
  };

  ws.onerror = () => {
    // Don't call close() here — onclose will fire naturally and trigger reconnection
  };
}

function disconnectWS() {
  _stopProgressWatchdog();
  if (reconnectTimer) clearTimeout(reconnectTimer);
  reconnectTimer = null;
  if (ws) {
    ws.onclose = null; // Prevent auto-reconnect
    ws.close();
    ws = null;
  }
}

// ── WS Message Handlers ────────────────────────────────

function handleProgress(msg) {
  _touchProgress();
  const agent = msg.agent;
  const percent = msg.percent ?? 0;
  // 映射到 SMR 步骤
  const agentMap = { "chapter_parser":"scout_agent", "character_agent":"hitl", "scene_agent":"map_agent", "script_agent":"map_agent" };
  const mappedAgent = agentMap[agent] || agent;

  document.getElementById("progress-fill").style.width = (percent * 100) + "%";
  document.getElementById("progress-percent").textContent = Math.round(percent * 100) + "%";

  // 从 agent 推导 status 用于 UI 渲染
  const agentStatusMap = {
    "chapter_parser": "parsing", "character_agent": "char_extracting",
    "scene_agent": "scene_segmenting", "script_agent": "script_generating",
    "scout_agent": "parsing", "hitl": "scout_hitl",
    "map_agent": "scene_segmenting", "validator": "validating",
  };
  const derivedStatus = agentStatusMap[agent] || State.status;
  renderPipelineUI({ current_agent: agent, progress: percent }, derivedStatus);

  const agentNames = {
    "chapter_parser": "章节解析", "character_agent": "角色识别",
    "scene_agent": "场景切分", "script_agent": "剧本生成",
    "scout_agent": "全局侦察 (Scout)",
    "map_agent": "切片转换 (Map)",
    "validator": "校验合并 (Reduce)",
  };

  if (agentNames[agent]) {
    addLog("info", `${agentNames[agent]}进行中... (${Math.round(percent * 100)}%)`);
  }
}

function handleTokenStream(msg) {
  // Append to a streaming output if needed
  // For now just log chunks
  if (msg.chunk) {
    // Token streaming can be added later for real-time output preview
  }
}

function handleHITLPause(msg) {
  _stopProgressWatchdog();
  addLog("warn", `Pipeline 暂停 — ${msg.reason || "需要人工干预"}`);
  document.getElementById("status-badge").textContent = "等待审阅";
  document.getElementById("status-badge").className = "status-badge paused";

  renderHITL(msg, msg.data);
  const hitlStatusMap = {
    "character_agent": "char_hitl", "scene_agent": "scene_hitl",
    "script_agent": "script_hitl", "scout_agent": "scout_hitl",
  };
  renderPipelineUI(
    { current_agent: msg.agent, progress: State.progress },
    hitlStatusMap[msg.agent] || "paused"
  );
}

function handleStageComplete(msg) {
  _touchProgress();
  const agentNames = {
    "scout_agent": "全局扫描完成",
    "map_agent": "切片转换完成",
    "validator": "校验合并完成",
  };
  addLog("success", agentNames[msg.agent] || `${msg.agent} 完成`);
}

function handleError(msg) {
  _stopProgressWatchdog();
  addLog("error", msg.message || "未知错误");
  State.status = "error";
  document.getElementById("status-badge").textContent = "错误";
  document.getElementById("status-badge").className = "status-badge error";
  document.getElementById("btn-start").disabled = false;
  document.getElementById("btn-start").textContent = "重新转换";

  // Mark current step as error
  if (msg.agent) {
    const step = document.querySelector(`.step[data-agent="${msg.agent}"]`);
    const icon = document.getElementById("icon-" + msg.agent);
    if (step) step.classList.add("error");
    if (icon) { icon.textContent = "✗"; }
  }
}

function handleWSComplete(msg) {
  _stopProgressWatchdog();
  State.status = "completed";
  if (msg.result?.script_yaml) {
    State.yamlContent = msg.result.script_yaml;
    document.getElementById("yaml-content").textContent = msg.result.script_yaml;
    document.getElementById("result-panel").style.display = "block";
  }
  document.getElementById("status-badge").textContent = "已完成";
  document.getElementById("status-badge").className = "status-badge completed";
  document.getElementById("progress-fill").style.width = "100%";
  document.getElementById("progress-percent").textContent = "100%";
  document.getElementById("btn-start").disabled = true;
  document.getElementById("btn-start").textContent = "已完成";

  renderPipelineUI({ current_agent: "validator", progress: 1.0 }, "completed");
  addLog("success", "全部完成！剧本已生成");
}

/* ═══════════════════════════════════════════════════════════
   HELPERS
   ═══════════════════════════════════════════════════════════ */

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

function esc(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/"/g, "&quot;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

/* ── Keyboard shortcut ──────────────────────────────────── */
document.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && e.ctrlKey && State.view === "landing") {
    submitNovel();
  }
});
