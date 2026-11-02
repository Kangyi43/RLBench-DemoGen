
"use strict";

const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];

const state = {
  tasks: [],
  selected: new Set(),
  imgSize: 128,
  preview: { task: null, variation: -1, variationCount: 0, data: null },
  jobTimer: null,
  currentJobId: null,
  logOffset: 0,
  viewer: { task: null, episode: null, steps: 0, step: 0, cam: "front", stream: "rgb", playTimer: null },
};

function toast(msg, kind = "") {
  const el = document.createElement("div");
  el.className = `toast ${kind}`;
  el.textContent = msg;
  $("#toasts").appendChild(el);
  setTimeout(() => el.remove(), 4200);
}

async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail || detail; } catch {}
    throw new Error(detail);
  }
  return res.json();
}

$$("#mainTabs .tab").forEach((btn) =>
  btn.addEventListener("click", () => {
    $$("#mainTabs .tab").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    $$(".page").forEach((p) => p.classList.remove("active"));
    $(`#page-${btn.dataset.tab}`).classList.add("active");
    if (btn.dataset.tab === "browse") loadDatasets();
  })
);

function renderTasks() {
  const q = $("#taskSearch").value.trim().toLowerCase();
  const grid = $("#taskGrid");
  grid.innerHTML = "";
  state.tasks
    .filter((t) => t.toLowerCase().includes(q))
    .forEach((t) => {
      const el = document.createElement("div");
      el.className = "task-item" + (state.selected.has(t) ? " selected" : "");
      el.innerHTML = `
        <div class="task-thumb" data-task="${t}">${t.slice(0, 2)}</div>
        <div class="task-name" title="${t}">${t}</div>`;
      el.addEventListener("click", () => {
        state.selected.has(t) ? state.selected.delete(t) : state.selected.add(t);
        renderTasks();
        updateSelInfo();
      });
      grid.appendChild(el);
    });

  state.tasks.forEach((t) => {
    const thumb = localStorage.getItem(`thumb_${t}`);
    const holder = grid.querySelector(`.task-thumb[data-task="${t}"]`);
    if (thumb && holder) holder.innerHTML = `<img src="data:image/jpeg;base64,${thumb}">`;
  });
}

function updateSelInfo() {
  $("#selCount").textContent = state.selected.size;
  $("#selTotal").textContent = state.selected.size * +$("#episodes").value;
}

$("#taskSearch").addEventListener("input", renderTasks);
$("#btnAll").addEventListener("click", () => {
  state.tasks.forEach((t) => state.selected.add(t));
  renderTasks(); updateSelInfo();
});
$("#btnNone").addEventListener("click", () => {
  state.selected.clear();
  renderTasks(); updateSelInfo();
});

$("#episodes").addEventListener("input", (e) => {
  $("#epVal").textContent = e.target.value; updateSelInfo();
});
$("#workers").addEventListener("input", (e) => ($("#wkVal").textContent = e.target.value));
$$("#imgSize .seg-btn").forEach((b) =>
  b.addEventListener("click", () => {
    $$("#imgSize .seg-btn").forEach((x) => x.classList.remove("active"));
    b.classList.add("active");
    state.imgSize = +b.dataset.v;
  })
);
$("#btnDice").addEventListener("click", () => {
  $("#seed").value = Math.floor(Math.random() * 99999);
});

function collectConfig() {
  return {
    tasks: [...state.selected],
    episodes: +$("#episodes").value,
    image_size: [state.imgSize, state.imgSize],
    workers: +$("#workers").value,
    seed: +$("#seed").value || 42,
    demo_attempts: +$("#attempts").value || 10,
    layout: "all_variations",
    overwrite: $("#overwrite").checked,
  };
}

function toYAML(obj, indent = 0) {
  const pad = " ".repeat(indent);
  return Object.entries(obj)
    .map(([k, v]) => {
      if (Array.isArray(v))
        return `${pad}${k}: [${v.map((x) => (typeof x === "string" ? `"${x}"` : x)).join(", ")}]`;
      if (v && typeof v === "object") return `${pad}${k}:\n${toYAML(v, indent + 2)}`;
      return `${pad}${k}: ${typeof v === "string" ? `"${v}"` : v}`;
    })
    .join("\n");
}

$("#btnExport").addEventListener("click", () => {
  const cfg = collectConfig();
  const yaml = "# RLBench DemoGen · 生成配置\n\n" + toYAML(cfg) + "\n";
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([yaml], { type: "text/yaml" }));
  a.download = "demogen_config.yaml";
  a.click();
  toast("配置已导出为 demogen_config.yaml", "ok");
});

$("#btnVerify").addEventListener("click", async () => {
  toast("校验中…");
  try {
    const r = await api("/api/verify", { method: "POST" });
    const s = r.summary || {};
    if (s.failed) toast(`校验完成：${s.ok}/${s.total} 通过，${s.failed} 失败`, "err");
    else toast(`校验通过：${s.total} 个 episode 完整`, "ok");
  } catch (e) { toast(`校验失败：${e.message}`, "err"); }
});

function renderPreview(result) {
  state.preview.data = result;
  state.preview.variation = result.variation;
  state.preview.variationCount = result.variation_count;
  $("#pvVar").textContent = `variation ${result.variation} / ${result.variation_count}`;
  $("#pvMeta").innerHTML =
    `渲染耗时 ${result.render_seconds}s · 指令：` +
    result.language_instructions.map((d) => `「${d}」`).join(" ");
  const order = ["front", "left_shoulder", "right_shoulder", "overhead", "wrist"];
  $("#pvStage").innerHTML = `<div class="pv-grid">` +
    order.map((cam, i) => `
      <div class="pv-cell ${i === 0 ? "main" : ""}">
        <img src="data:image/jpeg;base64,${result.views[cam]}">
        <div class="pv-label">${cam}</div>
      </div>`).join("") + `</div>`;

  const t = state.preview.task;
  if (t) {
    localStorage.setItem(`thumb_${t}`, result.views.front);
    renderTasks();
  }
}

async function doPreview(variation = -1) {
  const task = state.preview.task || [...state.selected][0];
  if (!task) { toast("请先选择一个任务", "err"); return; }
  state.preview.task = task;
  $("#pvStage").innerHTML = `<div class="pv-grid">` +
    Array.from({ length: 5 }, () => `<div class="pv-cell shimmer"></div>`).join("") + `</div>`;
  $("#pvMeta").textContent = `正在渲染 ${task}（首次需启动仿真器，约 20–40s）…`;
  try {
    const r = await api("/api/preview", {
      method: "POST",
      body: JSON.stringify({ task, variation, seed: +$("#seed").value || 42 }),
    });
    renderPreview(r);
  } catch (e) {
    $("#pvMeta").textContent = "";
    $("#pvStage").innerHTML = `<div class="preview-empty"><div class="empty-glyph">⚠</div>
      <div>${e.message}</div><div class="hint">如持续失败可点击「↻ 新随机」重置仿真器</div></div>`;
    toast(`预览失败：${e.message}`, "err");
  }
}

$("#btnPreview").addEventListener("click", () => doPreview(-1));
$("#pvNew").addEventListener("click", () => doPreview(-1));
$("#pvPrev").addEventListener("click", () => {
  const v = (state.preview.variation - 1 + state.preview.variationCount) % state.preview.variationCount || 0;
  doPreview(v);
});
$("#pvNext").addEventListener("click", () => {
  const v = (state.preview.variation + 1) % state.preview.variationCount || 0;
  doPreview(v);
});

function renderJob(job) {
  const badge = $("#jobBadge");
  badge.className = `badge ${job.status}`;
  badge.textContent = { running: "运行中", done: "已完成", failed: "失败", stopping: "中断中", stopped: "已中断" }[job.status] || job.status;
  $("#btnStop").hidden = !(job.status === "running" || job.status === "stopping");
  const pct = job.total ? Math.round((job.progress / job.total) * 100) : 0;
  $("#progFill").style.width = `${pct}%`;
  $("#progText").textContent = `${job.progress} / ${job.total} 集 · ${pct}%`;

  const term = $("#term");
  term.innerHTML = "";
  for (const line of job.logs) {
    const div = document.createElement("div");
    div.className = "term-line" + (line.includes("saved") ? " ok" : line.includes("GIVING UP") || line.includes("FAILED") ? " err" : "");
    div.textContent = line;
    term.appendChild(div);
  }
  term.scrollTop = term.scrollHeight;
}

async function pollJob(id) {
  try {
    const job = await api(`/api/jobs/${id}`);
    renderJob(job);
    if (job.status === "running" || job.status === "stopping") {
      state.jobTimer = setTimeout(() => pollJob(id), 1500);
    } else {
      state.jobTimer = null;
      $("#btnGenerate").disabled = false;
      const msg = { done: `生成完成：${job.progress} 集`, stopped: "生成任务已中断", failed: `生成失败：${job.error || "见日志"}` }[job.status] || job.status;
      toast(msg, job.status === "failed" ? "err" : "ok");
    }
  } catch (e) {
    state.jobTimer = null;
    $("#btnGenerate").disabled = false;
    toast(`任务状态获取失败：${e.message}`, "err");
  }
}

$("#btnStop").addEventListener("click", async () => {
  const running = state.currentJobId;
  if (!running) return;
  $("#btnStop").disabled = true;
  try {
    await api(`/api/jobs/${running}/stop`, { method: "POST" });
    toast("中断指令已发送", "ok");
    pollJob(running);
  } catch (e) {
    toast(`中断失败：${e.message}`, "err");
    $("#btnStop").disabled = false;
  }
});

$("#btnGenerate").addEventListener("click", async () => {
  const cfg = collectConfig();
  if (!cfg.tasks.length) { toast("请至少选择一个任务", "err"); return; }
  $("#btnGenerate").disabled = true;
  $("#term").innerHTML = `<div class="term-line dim">— 启动任务：${cfg.tasks.length} 任务 × ${cfg.episodes} 集 · ${cfg.workers} workers —</div>`;
  try {
    const r = await api("/api/generate", { method: "POST", body: JSON.stringify(cfg) });
    toast(`任务已启动（${r.job_id}）`, "ok");
    state.currentJobId = r.job_id;
    state.logOffset = 0;
    pollJob(r.job_id);
  } catch (e) {
    $("#btnGenerate").disabled = false;
    toast(`启动失败：${e.message}`, "err");
  }
});

$("#btnClearLog").addEventListener("click", () => {
  $("#term").innerHTML = `<div class="term-line dim">— 等待任务 —</div>`;
  $("#progFill").style.width = "0%";
  $("#progText").textContent = "0 / 0";
});

async function loadDatasets() {
  const list = $("#dsList");
  try {
    const ds = await api("/api/datasets");
    if (!ds.length) {
      list.innerHTML = `<div class="empty-glyph sm">◌</div>
        <div class="hint" style="text-align:center">尚无数据 · 在「配置生成」页先生成</div>`;
      return;
    }
    list.innerHTML = "";
    for (const t of ds) {
      const el = document.createElement("div");
      el.className = "ds-task";
      el.innerHTML = `
        <div class="ds-task-head">
          <span class="ds-task-name">${t.task}</span>
          <span class="ds-task-count">${t.complete}/${t.episodes.length} 集</span>
        </div>
        <div class="ds-eps" hidden></div>`;
      const eps = el.querySelector(".ds-eps");
      t.episodes.forEach((e) => {
        const chip = document.createElement("span");
        chip.className = "ep-chip" + (e.complete ? "" : " bad");
        chip.textContent = e.name.replace("episode", "ep");
        chip.addEventListener("click", (ev) => {
          ev.stopPropagation();
          $$(".ep-chip").forEach((c) => c.classList.remove("active"));
          chip.classList.add("active");
          loadEpisode(t.task, e);
        });
        eps.appendChild(chip);
      });
      el.querySelector(".ds-task-head").addEventListener("click", () => {
        el.classList.toggle("open");
        eps.hidden = !eps.hidden;
      });
      list.appendChild(el);
    }
  } catch (e) {
    list.innerHTML = `<div class="hint">加载失败：${e.message}</div>`;
  }
}

function loadEpisode(task, ep) {
  const v = state.viewer;
  v.task = task; v.episode = ep.name;
  v.steps = ep.num_steps || 0; v.step = 0;
  $("#viewerTitle").textContent = `${task} / ${ep.name}`;
  $("#epMeta").textContent = (ep.instructions || []).join(" / ") || "";
  const range = $("#stepRange");
  range.max = Math.max(0, v.steps - 1); range.value = 0;
  $("#scrubber").hidden = false;
  showFrame();
}

function showFrame() {
  const v = state.viewer;
  if (!v.task) return;
  $("#stepLabel").textContent = `step ${v.step} / ${Math.max(0, v.steps - 1)}`;
  $("#viewerStage").innerHTML =
    `<img src="/api/datasets/${v.task}/${v.episode}/frame?cam=${v.cam}&stream=${v.stream}&step=${v.step}&t=${Date.now()}">`;
}

$("#stepRange").addEventListener("input", (e) => {
  state.viewer.step = +e.target.value;
  showFrame();
});
$("#camSel").addEventListener("change", (e) => {
  state.viewer.cam = e.target.value; showFrame();
});
$$("#streamSeg .seg-btn").forEach((b) =>
  b.addEventListener("click", () => {
    $$("#streamSeg .seg-btn").forEach((x) => x.classList.remove("active"));
    b.classList.add("active");
    state.viewer.stream = b.dataset.v;
    showFrame();
  })
);
$("#btnPlay").addEventListener("click", () => {
  const v = state.viewer;
  if (v.playTimer) {
    clearInterval(v.playTimer); v.playTimer = null;
    $("#btnPlay").textContent = "▶";
    return;
  }
  $("#btnPlay").textContent = "⏸";
  v.playTimer = setInterval(() => {
    v.step = (v.step + 1) % Math.max(1, v.steps);
    $("#stepRange").value = v.step;
    showFrame();
  }, 220);
});
$("#btnRefreshDs").addEventListener("click", loadDatasets);

(async function init() {
  try {
    const r = await api("/api/tasks");
    state.tasks = r.tasks;
    renderTasks();
    updateSelInfo();
  } catch (e) {
    toast(`后端连接失败：${e.message}`, "err");
  }
})();
