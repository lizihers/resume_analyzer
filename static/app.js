// ── State ──────────────────────────────────────────────────────
const state = {
  resumeText: "",
  resumeFilename: "",
  analysisResult: null,
  currentAnalysisId: null,
  token: localStorage.getItem("resume_token") || "",
  username: "",
};

// ── DOM refs ───────────────────────────────────────────────────
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

// ── API helper ─────────────────────────────────────────────────
async function api(path, options = {}) {
  const headers = options.headers || {};
  if (state.token) headers["Authorization"] = `Bearer ${state.token}`;
  if (!(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }
  return fetch(path, { ...options, headers });
}

// ── Auth ───────────────────────────────────────────────────────
let authMode = "login";

$("#authSubmit").textContent = "登录";

$$(".auth-tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    authMode = tab.dataset.auth;
    $$(".auth-tab").forEach((t) => t.classList.remove("active"));
    tab.classList.add("active");
    $("#authSubmit").textContent = authMode === "login" ? "登录" : "注册";
    hide("authError");
  });
});

$("#authForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const username = $("#authUsername").value.trim();
  const password = $("#authPassword").value.trim();
  if (!username || !password) return;

  hide("authError");
  $("#authSubmit").disabled = true;
  $("#authSubmit").textContent = authMode === "login" ? "登录中..." : "注册中...";

  try {
    const resp = await fetch(`/api/${authMode}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });

    if (!resp.ok) {
      const err = await resp.text();
      let msg = err;
      try { msg = JSON.parse(err).detail || err; } catch (_) {}
      showError("authError", msg);
      return;
    }

    const data = await resp.json();
    state.token = data.token;
    state.username = data.username;
    localStorage.setItem("resume_token", data.token);
    showApp();
  } catch (e) {
    showError("authError", `网络错误: ${e.message}`);
  } finally {
    $("#authSubmit").disabled = false;
    $("#authSubmit").textContent = authMode === "login" ? "登录" : "注册";
  }
});

// Enter key submits auth form
$("#authPassword").addEventListener("keydown", (e) => {
  if (e.key === "Enter") e.preventDefault();
});

// Logout
$("#logoutBtn").addEventListener("click", () => {
  localStorage.removeItem("resume_token");
  state.token = "";
  state.username = "";
  state.resumeText = "";
  state.analysisResult = null;
  state.currentAnalysisId = null;
  hide("appMain");
  hide("mainHeader");
  hide("analysisResult");
  hide("parseInfo");
  show("uploadZone");
  show("authScreen");
  $("#authUsername").value = "";
  $("#authPassword").value = "";
});

async function initAuth() {
  if (!state.token) {
    show("authScreen");
    hide("mainHeader");
    hide("appMain");
    return;
  }
  try {
    const resp = await api("/api/me");
    if (!resp.ok) throw new Error("token invalid");
    const user = await resp.json();
    state.username = user.username;
    showApp();
  } catch (e) {
    localStorage.removeItem("resume_token");
    state.token = "";
    show("authScreen");
    hide("mainHeader");
    hide("appMain");
  }
}

function showApp() {
  hide("authScreen");
  show("mainHeader");
  show("appMain");
  $("#userInfo").textContent = state.username;
  checkHealth();
  updateMatchButton();
  updateRecommendButton();
}

// ── Tab switching ──────────────────────────────────────────────
$$(".tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    $$(".tab").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    $$(".tab-content").forEach((s) => s.classList.remove("active"));
    $(`#tab-${btn.dataset.tab}`).classList.add("active");

    if (btn.dataset.tab === "history") loadHistory();
    if (btn.dataset.tab === "match") updateMatchButton();
  });
});

// ── Upload ─────────────────────────────────────────────────────
const uploadZone = $("#uploadZone");
const fileInput = $("#fileInput");

uploadZone.addEventListener("click", () => fileInput.click());
$("#selectBtn").addEventListener("click", (e) => {
  e.stopPropagation();
  fileInput.click();
});

uploadZone.addEventListener("dragover", (e) => {
  e.preventDefault();
  uploadZone.classList.add("drag-over");
});
uploadZone.addEventListener("dragleave", () => uploadZone.classList.remove("drag-over"));
uploadZone.addEventListener("drop", (e) => {
  e.preventDefault();
  uploadZone.classList.remove("drag-over");
  const file = e.dataTransfer.files[0];
  if (file) handleFile(file);
});

fileInput.addEventListener("change", () => {
  const file = fileInput.files[0];
  if (file) handleFile(file);
});

async function handleFile(file) {
  const ext = file.name.split(".").pop().toLowerCase();
  if (!["pdf", "docx", "doc"].includes(ext)) {
    showError("parseError", "仅支持 PDF / DOCX / DOC 格式");
    return;
  }

  hide("parseError");
  const form = new FormData();
  form.append("file", file);

  try {
    const resp = await api("/api/parse", { method: "POST", body: form });
    if (!resp.ok) {
      const err = await resp.text();
      showError("parseError", `解析失败: ${err}`);
      return;
    }
    const data = await resp.json();
    state.resumeText = data.text;
    state.resumeFilename = data.filename;

    $("#fileName").textContent = data.filename;
    const maskedTag = data.masked ? " (已脱敏)" : "";
    $("#fileChars").textContent = `${data.char_count} 字符${maskedTag}`;
    $("#resumePreview").textContent = data.text.slice(0, 3000);
    if (data.text.length > 3000) $("#resumePreview").textContent += "\n...[截断]";

    hide("uploadZone");
    show("parseInfo");
    hide("analysisResult");
    hide("analysisError");
  } catch (e) {
    showError("parseError", `网络错误: ${e.message}`);
  }
}

// ── Analyze ────────────────────────────────────────────────────
$("#analyzeBtn").addEventListener("click", async () => {
  if (!state.resumeText) return;

  show("analyzeLoading");
  hide("analysisResult");
  hide("analysisError");
  $("#analyzeBtn").disabled = true;

  try {
    const resp = await api("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        resume_text: state.resumeText,
        filename: state.resumeFilename,
        save: true,
      }),
    });

    if (!resp.ok) {
      const err = await resp.text();
      showError("analysisError", `分析失败: ${err}`);
      return;
    }

    const data = await resp.json();
    if (data.result.error) {
      showError("analysisError", data.result.error);
      return;
    }

    state.analysisResult = data.result;
    state.currentAnalysisId = data.analysis_id;
    renderAnalysis(data.result);
    show("analysisResult");
    updateRecommendButton();
  } catch (e) {
    showError("analysisError", `网络错误: ${e.message}`);
  } finally {
    hide("analyzeLoading");
    $("#analyzeBtn").disabled = false;
  }
});

function renderAnalysis(r) {
  // Education analysis
  const ea = r.education_analysis;
  if (ea && ea.school_tier) {
    let tierClass = "tier-normal";
    if (/985|211|双一流|C9|清华|北大/.test(ea.school_tier)) tierClass = "tier-high";
    else if (/一本|省重点|双非一本/.test(ea.school_tier)) tierClass = "tier-mid";
    $("#eduAnalysis").innerHTML = `
      <div class="edu-card">
        <div class="edu-tier ${tierClass}">${ea.school_tier || ""}</div>
        <div>
          <span class="edu-label">学历层次</span>
          <span class="edu-val">${ea.level || ""}</span>
          <span class="edu-label" style="margin-left:12px">专业匹配</span>
          <span class="edu-val">${ea.major_match || 0}/100</span>
          <span class="edu-label" style="margin-left:12px">竞争力</span>
          <span class="edu-val">${ea.competitiveness || 0}/100</span>
        </div>
        <div style="grid-column:1/-1;font-size:13px;color:var(--green)">${ea.advantage || ""}</div>
        <div style="grid-column:1/-1;font-size:13px;color:var(--text-dim)">${ea.limitation || ""}</div>
      </div>`;
    show("eduAnalysisSection");
  } else {
    hide("eduAnalysisSection");
  }

  // Scores
  const sc = r.score || {};
  const scores = [
    ["完整度", sc.completeness || 0],
    ["影响力", sc.impact || 0],
    ["关键词", sc.keyword || 0],
    ["综合", sc.overall || 0],
  ];
  $("#scoreRow").innerHTML = scores
    .map(
      ([label, val]) =>
        `<div class="score-card">
          <div class="score-val">${val}</div>
          <div class="score-label">${label}</div>
          <div class="score-bar"><div class="score-bar-fill" style="width:${val}%"></div></div>
        </div>`
    )
    .join("");

  // Skills
  const techTags = (r.skills?.technical || []).map((s) => `<span class="tag tag-tech">${s}</span>`).join(" ");
  const softTags = (r.skills?.soft || []).map((s) => `<span class="tag tag-soft">${s}</span>`).join(" ");
  $("#skillsArea").innerHTML = `<div class="tag-row">${techTags}${softTags}</div>`;

  // Experience
  const exps = r.experience || [];
  if (exps.length === 0) {
    $("#expArea").innerHTML = '<p style="color:var(--text-dim)">未识别到经历</p>';
  } else {
    $("#expArea").innerHTML = exps
      .map(
        (e) =>
          `<div class="exp-card">
            <div class="exp-title">${e.title || ""}</div>
            <div class="exp-org">${e.company || ""}${e.duration ? " · " + e.duration : ""}</div>
            ${(e.highlights || []).map((h) => `<div class="exp-hl">${h}</div>`).join("")}
          </div>`
      )
      .join("");
  }

  // Strengths & weaknesses
  $("#strengthsList").innerHTML = (r.strengths || []).map((s) => `<li>${s}</li>`).join("");
  $("#weaknessesList").innerHTML = (r.weaknesses || []).map((w) => `<li>${w}</li>`).join("");

  // Suggestions
  const sugHTML = (r.suggestions || [])
    .map(
      (s) =>
        `<div class="suggestion-item">
          <span class="sug-cat cat-${s.category || "content"}">${s.category || "content"}</span>
          ${s.advice || ""}
        </div>`
    )
    .join("");
  $("#suggestionsList").innerHTML = sugHTML || '<p style="color:var(--text-dim)">无</p>';
}

// ── Match ──────────────────────────────────────────────────────
$("#matchBtn").addEventListener("click", async () => {
  const jobText = $("#jobDesc").value.trim();
  if (!state.resumeText || !jobText) return;

  show("matchLoading");
  hide("matchResult");
  hide("matchError");
  $("#matchBtn").disabled = true;

  try {
    const resp = await api("/api/match", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        resume_text: state.resumeText,
        job_text: jobText,
        analysis_id: state.currentAnalysisId,
      }),
    });

    if (!resp.ok) {
      const err = await resp.text();
      showError("matchError", `匹配失败: ${err}`);
      return;
    }

    const data = await resp.json();
    if (data.result.error) {
      showError("matchError", data.result.error);
      return;
    }

    renderMatch(data.result);
    show("matchResult");
  } catch (e) {
    showError("matchError", `网络错误: ${e.message}`);
  } finally {
    hide("matchLoading");
    $("#matchBtn").disabled = false;
  }
});

function renderMatch(r) {
  const ms = r.match_score || 0;
  $("#matchScoreBig").innerHTML = `
    <div class="big-num">${ms}</div>
    <div class="big-label">匹配度 / 100</div>
    <div class="score-bar" style="margin-top:12px"><div class="score-bar-fill" style="width:${ms}%"></div></div>
  `;

  $("#matchSkills").innerHTML =
    (r.matching_skills || []).length > 0
      ? `<div class="tag-row">${(r.matching_skills || []).map((s) => `<span class="tag tag-match">${s}</span>`).join(" ")}</div>`
      : '<p style="color:var(--text-dim)">无</p>';

  $("#missSkills").innerHTML =
    (r.missing_skills || []).length > 0
      ? `<div class="tag-row">${(r.missing_skills || []).map((s) => `<span class="tag tag-miss">${s}</span>`).join(" ")}</div>`
      : '<p style="color:var(--text-dim)">无</p>';

  $("#gapsList").innerHTML = (r.gaps || []).map((g) => `<li>${g}</li>`).join("");
  $("#matchRecs").innerHTML = (r.recommendations || []).map((r) => `<li>${r}</li>`).join("");

  // Optimization directions
  const opt = r.optimization || {};
  const kw = opt.keywords_to_add || [];
  $("#optKeywords").innerHTML = kw.length > 0
    ? `<div class="tag-row">${kw.map((k) => `<span class="tag tag-match">${escapeHtml(k)}</span>`).join(" ")}</div>`
    : '<p style="color:var(--text-dim)">无</p>';

  const rewrite = opt.experience_rewrite || [];
  $("#optRewrite").innerHTML = rewrite.length > 0
    ? rewrite.map((rw) => `<div class="opt-rewrite-item">${escapeHtml(rw)}</div>`).join("")
    : '<p style="color:var(--text-dim)">无</p>';

  const priority = opt.skill_priority || [];
  if (priority.length > 0) {
    $("#optPriority").innerHTML = priority.map((p, i) => `
      <div class="opt-priority-item">
        <div class="opt-priority-rank">${i + 1}</div>
        <div>
          <div class="opt-priority-skill">${escapeHtml(typeof p === 'string' ? p : p.skill || '')}</div>
          <div class="opt-priority-reason">${escapeHtml(typeof p === 'object' ? p.reason || '' : '')}</div>
        </div>
      </div>`).join("");
  } else {
    $("#optPriority").innerHTML = '<p style="color:var(--text-dim)">无</p>';
  }

  show("optimizationSection");
}

function updateMatchButton() {
  const hasResume = state.resumeText.length > 0;
  const hasJob = $("#jobDesc").value.trim().length > 0;
  $("#matchBtn").disabled = !hasResume || !hasJob;
  if (!hasResume) {
    show("noResumeHint");
  } else {
    hide("noResumeHint");
  }
}

// ── Fetch JD from URL ──────────────────────────────────────────
$("#fetchJdBtn").addEventListener("click", async () => {
  const url = $("#jdUrl").value.trim();
  if (!url) return;
  const statusEl = $("#fetchStatus");
  const btn = $("#fetchJdBtn");
  btn.disabled = true;
  statusEl.textContent = "抓取中...";
  statusEl.className = "fetch-status";
  try {
    const resp = await api("/api/fetch-jd", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });
    if (!resp.ok) {
      const err = await resp.text();
      statusEl.textContent = "抓取失败";
      statusEl.className = "fetch-status err";
      showError("matchError", `抓取JD失败: ${err}`);
      return;
    }
    const data = await resp.json();
    $("#jobDesc").value = data.text;
    statusEl.textContent = `抓取成功 (${data.char_count} 字符)`;
    statusEl.className = "fetch-status ok";
    updateMatchButton();
  } catch (e) {
    statusEl.textContent = "网络错误";
    statusEl.className = "fetch-status err";
  } finally {
    btn.disabled = false;
  }
});

// Enter key in JD URL input triggers fetch
$("#jdUrl").addEventListener("keydown", (e) => {
  if (e.key === "Enter") $("#fetchJdBtn").click();
});

$("#jobDesc").addEventListener("input", updateMatchButton);

// ── Job Recommendations ────────────────────────────────────────
$("#recommendBtn").addEventListener("click", async () => {
  if (!state.resumeText) return;

  show("recLoading");
  hide("recResult");
  hide("recError");
  $("#recommendBtn").disabled = true;

  try {
    const resp = await api("/api/recommend-jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        resume_text: state.resumeText,
        filename: state.resumeFilename,
        save: false,
      }),
    });

    if (!resp.ok) {
      const err = await resp.text();
      showError("recError", `推荐失败: ${err}`);
      return;
    }

    const data = await resp.json();
    if (data.result.error) {
      showError("recError", data.result.error);
      return;
    }

    renderRecommendations(data.result);
    show("recResult");
  } catch (e) {
    showError("recError", `网络错误: ${e.message}`);
  } finally {
    hide("recLoading");
    $("#recommendBtn").disabled = false;
  }
});

function renderRecommendations(r) {
  // Positions — render the new position-level matching
  const positions = r.recommended_positions || [];
  if (positions.length > 0) {
    $("#recPositions").style.display = "";
    $("#recPositions").innerHTML = positions.map((p) => `
      <div class="position-card">
        <div class="pos-header">
          <div class="pos-match-score">${p.match_score || 0}%</div>
          <div class="pos-info">
            <div class="pos-role">${escapeHtml(p.role || "")}</div>
            <div class="pos-salary">${escapeHtml(p.salary_range || "")}</div>
          </div>
        </div>
        <div class="pos-assessment">${escapeHtml(p.fit_assessment || "")}</div>
        <div class="pos-skills">
          <div class="pos-skill-group">
            <span class="pos-skill-label match">已匹配</span>
            ${(p.matching_skills || []).map((s) => `<span class="tag tag-match">${escapeHtml(s)}</span>`).join("")}
          </div>
          <div class="pos-skill-group">
            <span class="pos-skill-label miss">需补充</span>
            ${(p.missing_skills || []).map((s) => `<span class="tag tag-miss">${escapeHtml(s)}</span>`).join("")}
          </div>
          ${(p.recruitment_urls || []).length > 0 ? `
          <div class="pos-recruit-links">
            ${p.recruitment_urls.map((u) => `<a href="${escapeHtml(u.url)}" target="_blank" class="recruit-link">${escapeHtml(u.name)} ↗</a>`).join("")}
          </div>` : ""}
        </div>
      </div>`).join("");
  } else {
    // Fallback to old format
    const dirs = r.recommended_directions || [];
    $("#recPositions").innerHTML = dirs.length > 0
      ? dirs.map((d) => `
        <div class="dir-card">
          <div class="dir-title">${escapeHtml(d.title || "")}</div>
          <div class="dir-salary">${escapeHtml(d.salary_range || "")}</div>
          <div class="dir-reason">${escapeHtml(d.fit_reason || "")}</div>
        </div>`).join("")
      : '<p style="color:var(--text-dim)">AI 正在分析中，请稍后重试</p>';
  }

  // Companies — updated format with position-specific matching
  const companies = r.target_companies || [];
  $("#recCompanies").innerHTML = companies.length > 0
    ? companies.map((c) => {
      const name = c.company_name || c.name || "";
      const reason = c.reason || c.match_reason || "";
      const matchPct = c.position_match ? ` · ${c.position_match}%` : "";
      const role = c.role ? `<div class="co-role">${escapeHtml(c.role)}${matchPct}</div>` : "";
      return `
      <div class="company-card">
        <span class="co-priority ${c.priority === 'high' ? 'priority-high' : 'priority-medium'}">${c.priority === 'high' ? '推荐' : '备选'}</span>
        <div>
          <div class="co-name">${escapeHtml(name)}</div>
          ${role}
          <div class="co-reason">${escapeHtml(reason)}</div>
        </div>
        ${c.career_url ? `<a href="${escapeHtml(c.career_url)}" target="_blank" class="co-link">招聘官网 ↗</a>` : ""}
      </div>`;
    }).join("")
    : '<p style="color:var(--text-dim)">无</p>';

  // Career advice
  const advice = r.career_advice || [];
  $("#recAdvice").innerHTML = advice.length > 0
    ? advice.map((a) => `<li>${escapeHtml(a)}</li>`).join("")
    : '<p style="color:var(--text-dim)">无</p>';
}

function updateRecommendButton() {
  const hasResume = state.resumeText.length > 0;
  const hasAnalysis = state.analysisResult !== null;
  $("#recommendBtn").disabled = !hasResume;
  if (!hasResume) {
    show("noResumeForRec");
  } else {
    hide("noResumeForRec");
  }
}

// ── History ────────────────────────────────────────────────────
async function loadHistory() {
  $("#historyBody").innerHTML = '<tr><td colspan="4" class="empty">加载中...</td></tr>';
  try {
    const resp = await api("/api/history");
    const rows = await resp.json();
    if (rows.length === 0) {
      $("#historyBody").innerHTML = '<tr><td colspan="4" class="empty">暂无记录</td></tr>';
      return;
    }
    $("#historyBody").innerHTML = rows
      .map(
        (r) =>
          `<tr>
            <td>#${r.id}</td>
            <td>${escapeHtml(r.filename)}</td>
            <td>${r.created_at || ""}</td>
            <td>
              <button class="btn btn-sm btn-outline load-btn" data-id="${r.id}">查看</button>
              <button class="btn btn-sm btn-danger del-btn" data-id="${r.id}">删除</button>
            </td>
          </tr>`
      )
      .join("");

    // Bind load buttons
    $$(".load-btn").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const id = btn.dataset.id;
        const resp = await api(`/api/history/${id}`);
        if (!resp.ok) return;
        const record = await resp.json();
        state.resumeText = record.resume_text;
        state.resumeFilename = record.filename;
        state.currentAnalysisId = record.id;
        if (record.analysis_json && typeof record.analysis_json === "object") {
          state.analysisResult = record.analysis_json;
          renderAnalysis(record.analysis_json);
          show("analysisResult");
          hide("uploadZone");
          show("parseInfo");
          $("#fileName").textContent = record.filename;
          $("#fileChars").textContent = `${record.resume_text.length} 字符`;
          $("#resumePreview").textContent = record.resume_text.slice(0, 3000);
        }
        // Switch to analyze tab
        $$(".tab").forEach((b) => b.classList.remove("active"));
        $('[data-tab="analyze"]').classList.add("active");
        $$(".tab-content").forEach((s) => s.classList.remove("active"));
        $("#tab-analyze").classList.add("active");
        updateMatchButton();
      });
    });

    // Bind delete buttons
    $$(".del-btn").forEach((btn) => {
      btn.addEventListener("click", async () => {
        if (!confirm("确定删除?")) return;
        const id = btn.dataset.id;
        await api(`/api/history/${id}`, { method: "DELETE" });
        loadHistory();
      });
    });
  } catch (e) {
    $("#historyBody").innerHTML = `<tr><td colspan="4" class="empty">加载失败: ${e.message}</td></tr>`;
  }
}

// ── Health check ──────────────────────────────────────────────
async function checkHealth() {
  try {
    const resp = await api("/api/health");
    const data = await resp.json();
    const badge = $("#apiStatus");
    const providerLabel = data.api_provider === "ollama" ? "🆓 Ollama(免费)" :
                          data.api_provider === "siliconflow" ? "SF(免费)" :
                          data.api_provider === "deepseek" ? "DS(付费)" : data.api_provider;
    if (data.api_configured) {
      badge.textContent = `${providerLabel} | ${data.model}`;
      badge.className = "api-badge ok";
    } else {
      badge.textContent = "API 未配置 → 编辑 .env";
      badge.className = "api-badge err";
    }
  } catch (e) {
    $("#apiStatus").textContent = "API: 连接失败";
    $("#apiStatus").className = "api-badge err";
  }
}

// ── Helpers ────────────────────────────────────────────────────
function show(sel) {
  const el = $(`#${sel}`);
  if (el) el.style.display = "";
}
function hide(sel) {
  const el = $(`#${sel}`);
  if (el) el.style.display = "none";
}
function showError(elId, msg) {
  const el = $(`#${elId}`);
  if (el) {
    el.textContent = msg;
    el.style.display = "block";
  }
}
function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

// ── Init ───────────────────────────────────────────────────────
initAuth();
