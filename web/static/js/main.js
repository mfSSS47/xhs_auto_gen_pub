// ── Mode Selector ─────────────────────────────
(function () {
  const options = document.querySelectorAll(".mode-option");
  const modeInput = document.getElementById("mode-input");
  const submitBtn = document.getElementById("submit-btn");

  options.forEach((opt) => {
    opt.addEventListener("click", () => {
      options.forEach((o) => o.classList.remove("active"));
      opt.classList.add("active");
      const mode = opt.dataset.mode;
      modeInput.value = mode;
      submitBtn.textContent = mode === "preview" ? "生成内容预览" : "开始生成并发布";
    });
  });
})();

// ── Image Upload Preview ──────────────────────
(function () {
  const zone = document.getElementById("upload-zone");
  const input = document.getElementById("image-input");
  const previews = document.getElementById("image-previews");

  if (!zone || !input || !previews) return;

  let selectedFiles = [];

  zone.addEventListener("dragover", (e) => {
    e.preventDefault();
    zone.classList.add("drag-over");
  });
  zone.addEventListener("dragleave", () => zone.classList.remove("drag-over"));
  zone.addEventListener("drop", (e) => {
    e.preventDefault();
    zone.classList.remove("drag-over");
    addFiles(e.dataTransfer.files);
  });

  input.addEventListener("change", () => {
    addFiles(input.files);
    input.value = "";
  });

  function addFiles(newFiles) {
    for (const f of newFiles) {
      if (!f.type.startsWith("image/")) continue;
      selectedFiles.push(f);
    }
    renderPreviews();
  }

  function renderPreviews() {
    previews.innerHTML = "";
    selectedFiles.forEach((f, i) => {
      const div = document.createElement("div");
      div.className = "preview-item";

      const img = document.createElement("img");
      img.src = URL.createObjectURL(f);
      img.title = f.name;

      const btn = document.createElement("button");
      btn.className = "remove-btn";
      btn.textContent = "×";
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        selectedFiles.splice(i, 1);
        renderPreviews();
      });

      div.appendChild(img);
      div.appendChild(btn);
      previews.appendChild(div);
    });
  }

  // ── Form Submit ──────────────────────────────
  const form = document.getElementById("publish-form");
  const submitBtn = document.getElementById("submit-btn");
  const formStatus = document.getElementById("form-status");
  const modeInput = document.getElementById("mode-input");

  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    const title = document.getElementById("title").value.trim();
    const requirements = document.getElementById("requirements").value.trim();
    if (!title || !requirements) return;

    submitBtn.disabled = true;
    submitBtn.textContent = "提交中...";
    formStatus.textContent = "";

    const fd = new FormData();
    fd.append("title", title);
    fd.append("requirements", requirements);
    fd.append("mode", modeInput.value);
    for (const f of selectedFiles) {
      fd.append("images", f, f.name);
    }

    try {
      const resp = await fetch("/api/jobs", { method: "POST", body: fd });
      const data = await resp.json();
      if (data.error) {
        formStatus.textContent = data.error;
        submitBtn.disabled = false;
        submitBtn.textContent = modeInput.value === "preview" ? "生成内容预览" : "开始生成并发布";
      } else {
        window.location.href = "/status/" + data.job_id;
      }
    } catch (err) {
      formStatus.textContent = "网络错误，请重试";
      submitBtn.disabled = false;
      submitBtn.textContent = modeInput.value === "preview" ? "生成内容预览" : "开始生成并发布";
    }
  });
})();

// ── Status Polling ─────────────────────────────
(function () {
  if (typeof JOB_ID === "undefined") return;

  const statusText = document.getElementById("status-text");
  const spinner = document.getElementById("spinner");
  const errorBox = document.getElementById("error-box");
  const errorText = document.getElementById("error-text");
  const resultBox = document.getElementById("result-box");
  const previewBox = document.getElementById("preview-box");

  const STAGE_ORDER = [
    "queued", "in_progress", "creating_direction", "generating",
    "reviewing", "awaiting_approval", "publishing", "completed"
  ];

  function updateStages(currentStatus) {
    const idx = STAGE_ORDER.indexOf(currentStatus);
    document.querySelectorAll(".stage").forEach((el) => {
      const s = el.dataset.stage;
      const si = STAGE_ORDER.indexOf(s);
      el.classList.remove("active", "done");
      if (si >= 0 && si < idx) el.classList.add("done");
      if (si === idx) el.classList.add("active");
    });
  }

  async function poll() {
    try {
      const resp = await fetch("/api/jobs/" + JOB_ID);
      if (!resp.ok) { setTimeout(poll, 3000); return; }
      const job = await resp.json();

      statusText.textContent = job.progress_message || job.status;
      updateStages(job.status);

      // Preview mode: show content for approval
      if (job.status === "awaiting_approval") {
        if (spinner) spinner.style.display = "none";
        previewBox.classList.remove("hidden");
        document.getElementById("p-title").textContent = job.post_title || "";
        document.getElementById("p-body").textContent = job.post_body || "";
        document.getElementById("p-tags").textContent = (job.hashtags || []).join(", ");
        document.getElementById("p-score").textContent = job.review_score ? job.review_score + " / 10" : "";
        return;
      }

      // Completed
      if (job.status === "completed") {
        if (spinner) spinner.style.display = "none";
        resultBox.classList.remove("hidden");
        document.getElementById("r-title").textContent = job.post_title || "";
        document.getElementById("r-body").textContent = job.post_body || "";
        document.getElementById("r-hashtags").textContent = (job.hashtags || []).join(", ");
        document.getElementById("r-score").textContent = job.review_score || "";
        document.getElementById("r-platform").textContent = job.platform_post_id || "";
        return;
      }

      // Failed
      if (job.status === "failed") {
        if (spinner) spinner.style.display = "none";
        errorBox.classList.remove("hidden");
        errorText.textContent = job.error_message || "未知错误";
        return;
      }

      setTimeout(poll, 3000);
    } catch (err) {
      setTimeout(poll, 5000);
    }
  }

  poll();
})();

// ── Preview Approval Actions ─────────────────────
async function approveAndPublish() {
  const btn = document.getElementById("approve-btn");
  const status = document.getElementById("preview-status");
  btn.disabled = true;
  btn.textContent = "提交中...";
  status.textContent = "";

  try {
    const resp = await fetch("/api/jobs/" + JOB_ID + "/publish", { method: "POST" });
    const data = await resp.json();
    if (data.error) {
      status.textContent = data.error;
      btn.disabled = false;
      btn.textContent = "确认并发布";
    } else {
      // Hide preview, show spinner, resume polling
      document.getElementById("preview-box").classList.add("hidden");
      if (document.getElementById("spinner"))
        document.getElementById("spinner").style.display = "";
      document.getElementById("status-text").textContent = "正在发布...";
      // Reload to restart polling with new status
      window.location.reload();
    }
  } catch (err) {
    status.textContent = "网络错误，请重试";
    btn.disabled = false;
    btn.textContent = "确认并发布";
  }
}

function rejectPost() {
  window.location.href = "/";
}
