// ── Step animation ────────────────────────────────────────────────────────────
let _stepTimer = null;

function startSteps() {
  const steps = ["s1","s2","s3","s4"];
  const delays = [0, 3000, 8000, 14000];
  steps.forEach((id, i) => {
    setTimeout(() => {
      document.querySelectorAll(".step").forEach(el => el.classList.remove("active"));
      const el = document.getElementById(id);
      if (el) el.classList.add("active");
    }, delays[i]);
  });
}

function stopSteps() {
  document.querySelectorAll(".step").forEach(el => el.classList.remove("active"));
}

// ── File label ────────────────────────────────────────────────────────────────
function onFileChange() {
  const file = document.getElementById("resume").files[0];
  document.getElementById("uploadLabel").textContent = file
    ? "📄 " + file.name
    : "📄 Click to select PDF or DOCX";
}

// ── Score colour ──────────────────────────────────────────────────────────────
function scoreColor(s) {
  if (s >= 70) return "#22c55e";
  if (s >= 45) return "#f59e0b";
  return "#ef4444";
}

function scoreLabel(s) {
  if (s >= 70) return "Strong Match ✅";
  if (s >= 45) return "Partial Match ⚠️";
  return "Weak Match ❌";
}

// ── Tags HTML ─────────────────────────────────────────────────────────────────
function tags(arr, cls) {
  if (!arr || arr.length === 0)
    return `<span style="opacity:.5;font-size:.9rem">None detected</span>`;
  return arr.map(s => `<span class="tag ${cls}">${s}</span>`).join("");
}

// ── Experience rows ───────────────────────────────────────────────────────────
function expRanges(ranges) {
  if (!ranges || ranges.length === 0) return "";
  return `
    <div class="exp-ranges">
      <strong>Date ranges found:</strong>
      ${ranges.map(r => `<span class="range-tag">${r}</span>`).join("")}
    </div>`;
}

// ── Main submit ───────────────────────────────────────────────────────────────
async function uploadResume() {
  const jd     = document.getElementById("jd").value.trim();
  const file   = document.getElementById("resume").files[0];
  const result = document.getElementById("result");
  const loading= document.getElementById("loading");
  const errBox = document.getElementById("errorBox");
  const btn    = document.getElementById("screenBtn");

  errBox.classList.add("hidden");
  result.classList.add("hidden");

  if (!jd)   { showError("Please enter a job description."); return; }
  if (!file) { showError("Please upload a resume (PDF or DOCX)."); return; }

  const formData = new FormData();
  formData.append("jd",   jd);
  formData.append("file", file);

  loading.classList.remove("hidden");
  btn.disabled = true;
  btn.textContent = "Analyzing...";
  startSteps();

  try {
    const resp = await fetch("/screen", { method: "POST", body: formData });
    const data = await resp.json();

    if (!resp.ok) {
      showError(data.detail || "Something went wrong. Check your Ollama server.");
      return;
    }

    stopSteps();
    loading.classList.add("hidden");
    renderResult(result, data);

  } catch (err) {
    showError("Network error — is the server running?");
    console.error(err);
  } finally {
    loading.classList.add("hidden");
    btn.disabled = false;
    btn.textContent = "Analyze Resume";
    stopSteps();
  }
}

function showError(msg) {
  const errBox = document.getElementById("errorBox");
  document.getElementById("loading").classList.add("hidden");
  errBox.textContent = "⚠ " + msg;
  errBox.classList.remove("hidden");
}

function renderResult(container, d) {
  const exp = d.experience || {};
  const color = scoreColor(d.match_score);

  container.innerHTML = `
    <h2>AI Screening Result</h2>

    <!-- Score + Experience row -->
    <div class="score-box">
      <div class="score-item">
        <p>Match Score</p>
        <div class="score" style="color:${color}">${d.match_score}%</div>
        <div class="score-label" style="color:${color}">${scoreLabel(d.match_score)}</div>
      </div>
      <div class="score-item">
        <p>Total Experience</p>
        <div class="score exp-score">${exp.display || "Not detected"}</div>
        ${expRanges(exp.ranges_found)}
      </div>
    </div>

    <!-- Skills -->
    <div class="result-section">
      <h3>✅ Matched Skills <span class="count">${d.matched_skills.length}</span></h3>
      <div class="tags">${tags(d.matched_skills, "")}</div>
    </div>

    <div class="result-section">
      <h3>❌ Missing Skills <span class="count missing-count">${d.missing_skills.length}</span></h3>
      <div class="tags">${tags(d.missing_skills, "missing")}</div>
    </div>

    <!-- Explanation -->
    <div class="result-section explanation">
      <h3>🤖 AI Explanation</h3>
      <p>${d.explanation}</p>
    </div>
  `;
  container.classList.remove("hidden");
  container.scrollIntoView({ behavior: "smooth" });
}
