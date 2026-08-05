const form = document.getElementById("extract-form");
const fileInput = document.getElementById("file-input");
const dropzone = document.getElementById("dropzone");
const fileLabel = document.getElementById("file-label");
const modeSelect = document.getElementById("mode");
const fieldsWrap = document.getElementById("fields-wrap");
const statusEl = document.getElementById("status");
const results = document.getElementById("results");
const resultsBody = document.getElementById("results-body");
const resultsMeta = document.getElementById("results-meta");
const resultsTitle = document.getElementById("results-title");
const extractBtn = document.getElementById("extract-btn");
const resetBtn = document.getElementById("reset-btn");
const copyBtn = document.getElementById("copy-btn");

let lastPayload = null;

function setStatus(message, isError = false) {
  statusEl.textContent = message || "";
  statusEl.classList.toggle("is-error", Boolean(isError));
}

function syncMode() {
  fieldsWrap.hidden = modeSelect.value !== "fields";
}

function syncFileLabel() {
  const file = fileInput.files?.[0];
  fileLabel.textContent = file ? file.name : "or click to choose a .log file";
}

function renderFactorRows(ruleset) {
  const details = ruleset.field_details || [];
  if (details.length) {
    return details
      .map(
        (item, index) => `
      <tr style="animation-delay:${index * 28}ms">
        <td>${escapeHtml(item.name)}</td>
        <td>${escapeHtml(item.value ?? "—")}</td>
        <td>${escapeHtml(item.source ?? (item.found ? "" : "missing"))}</td>
      </tr>`
      )
      .join("");
  }

  return Object.entries(ruleset.fields || {})
    .map(
      ([name, value], index) => `
    <tr style="animation-delay:${index * 28}ms">
      <td>${escapeHtml(name)}</td>
      <td>${escapeHtml(value ?? "—")}</td>
      <td></td>
    </tr>`
    )
    .join("");
}

function renderFullRows(ruleset) {
  const rows = [];
  for (const item of ruleset.inputs || []) {
    rows.push({ name: item.name, value: item.value, source: "input" });
  }
  for (const item of ruleset.evaluations || []) {
    rows.push({
      name: item.name,
      value: item.value,
      source: `evaluation/${item.kind}`,
    });
  }
  for (const item of ruleset.outputs || []) {
    rows.push({ name: item.name, value: item.value, source: "output" });
  }
  return rows
    .map(
      (item, index) => `
    <tr style="animation-delay:${Math.min(index, 40) * 18}ms">
      <td>${escapeHtml(item.name)}</td>
      <td>${escapeHtml(item.value ?? "—")}</td>
      <td>${escapeHtml(item.source)}</td>
    </tr>`
    )
    .join("");
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function showResults(payload) {
  lastPayload = payload;
  const ruleset = payload.rulesets?.[0];
  if (!ruleset) {
    results.hidden = true;
    setStatus("No ruleset data returned.", true);
    return;
  }

  const header = payload.header || {};
  results.hidden = false;
  resultsTitle.textContent =
    payload.mode === "full" ? `Ruleset · ${ruleset.name}` : `Factors · ${ruleset.name}`;
  resultsMeta.textContent = [
    payload.filename,
    header.policy_no,
    header.project_id,
    ruleset.precondition?.status
      ? `precondition ${ruleset.precondition.status}`
      : null,
  ]
    .filter(Boolean)
    .join(" · ");

  resultsBody.innerHTML =
    payload.mode === "full" ? renderFullRows(ruleset) : renderFactorRows(ruleset);
}

async function onSubmit(event) {
  event.preventDefault();
  const file = fileInput.files?.[0];
  if (!file) {
    setStatus("Choose a log file first.", true);
    return;
  }

  const body = new FormData();
  body.append("file", file);
  body.append("ruleset", document.getElementById("ruleset").value || "Building");
  body.append("mode", modeSelect.value);
  body.append("fields", document.getElementById("fields").value || "");

  extractBtn.disabled = true;
  setStatus("Extracting…");

  try {
    const response = await fetch("/api/extract", { method: "POST", body });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || "Extract failed.");
    }
    showResults(payload);
    const count =
      payload.mode === "full"
        ? (payload.rulesets?.[0]?.inputs?.length || 0) +
          (payload.rulesets?.[0]?.evaluations?.length || 0) +
          (payload.rulesets?.[0]?.outputs?.length || 0)
        : Object.keys(payload.rulesets?.[0]?.fields || {}).length;
    setStatus(`Extracted ${count} values.`);
  } catch (error) {
    results.hidden = true;
    setStatus(error.message || "Extract failed.", true);
  } finally {
    extractBtn.disabled = false;
  }
}

function onReset() {
  form.reset();
  document.getElementById("ruleset").value = "Building";
  modeSelect.value = "building-factors";
  syncMode();
  syncFileLabel();
  results.hidden = true;
  resultsBody.innerHTML = "";
  lastPayload = null;
  setStatus("");
}

async function onCopy() {
  if (!lastPayload) return;
  const ruleset = lastPayload.rulesets?.[0];
  const data =
    lastPayload.mode === "full"
      ? ruleset
      : ruleset?.fields || {};
  await navigator.clipboard.writeText(JSON.stringify(data, null, 2));
  setStatus("Copied JSON to clipboard.");
}

["dragenter", "dragover"].forEach((eventName) => {
  dropzone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropzone.classList.add("is-dragover");
  });
});

["dragleave", "drop"].forEach((eventName) => {
  dropzone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropzone.classList.remove("is-dragover");
  });
});

dropzone.addEventListener("drop", (event) => {
  const file = event.dataTransfer?.files?.[0];
  if (!file) return;
  const transfer = new DataTransfer();
  transfer.items.add(file);
  fileInput.files = transfer.files;
  syncFileLabel();
});

fileInput.addEventListener("change", syncFileLabel);
modeSelect.addEventListener("change", syncMode);
form.addEventListener("submit", onSubmit);
resetBtn.addEventListener("click", onReset);
copyBtn.addEventListener("click", onCopy);

syncMode();
syncFileLabel();
