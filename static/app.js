const form = document.querySelector("#splice-form");
const timestampField = document.querySelector("#timestamp-field");
const timestampInput = document.querySelector("#timestamp");
const statusArea = document.querySelector("#status-area");
const generateButton = document.querySelector("#generate-button");
const placementInputs = document.querySelectorAll("input[name='placement']");
const placementGroup = document.querySelector("#placement-group");
const progressLabel = document.querySelector("#progress-label");
const progressFill = document.querySelector("#progress-fill");
const progressTrack = document.querySelector(".progress-track");
const progressPercent = document.querySelector("#progress-percent");

function updateTimestampVisibility() {
  const placement = document.querySelector("input[name='placement']:checked")?.value;
  const promoMode = document.querySelector("[data-clip-section='promo'] .clip-mode")?.value;
  const showTimestamp = promoMode !== "none" && placement === "custom";
  timestampField.hidden = !showTimestamp;
  timestampInput.required = showTimestamp;
  if (!showTimestamp) timestampInput.value = "";
}

function updateClipSection(section) {
  const mode = section.querySelector(".clip-mode").value;
  section.querySelectorAll(".clip-option").forEach((option) => {
    const active = option.dataset.modes.split(" ").includes(mode);
    option.hidden = !active;
    option.querySelectorAll("input[type='file'], input[type='text']").forEach((input) => {
      input.required = active && (input.type === "file" || input.name.endsWith("_name"));
    });
  });
  if (section.dataset.clipSection === "promo") {
    const enabled = mode !== "none";
    placementGroup.hidden = !enabled;
    placementInputs.forEach((input) => { input.disabled = !enabled; });
    updateTimestampVisibility();
  }
}

document.querySelectorAll("[data-clip-section]").forEach((section) => {
  const mode = section.querySelector(".clip-mode");
  mode.addEventListener("change", () => updateClipSection(section));
  updateClipSection(section);
});
placementInputs.forEach((input) => input.addEventListener("change", updateTimestampVisibility));
document.querySelectorAll(".delete-form").forEach((deleteForm) => {
  deleteForm.addEventListener("submit", (event) => {
    if (!window.confirm("Delete this saved clip? This cannot be undone.")) event.preventDefault();
  });
});
function setProgress(message, progress) {
  statusArea.hidden = false;
  statusArea.classList.add("active");
  progressLabel.textContent = message;
  progressFill.style.width = `${progress}%`;
  progressTrack.setAttribute("aria-valuenow", String(progress));
  progressPercent.textContent = `${progress}% complete`;
}

async function checkJob(jobId) {
  const response = await fetch(`/process-status/${jobId}`);
  const job = await response.json();
  if (!response.ok) throw new Error(job.error || "Could not read processing progress.");
  setProgress(job.message, job.progress);
  if (job.state === "complete") {
    statusArea.innerHTML = `<strong>Video processing complete</strong><span>${job.message}</span> <a href="${job.download_url}">Download finished video</a>`;
    generateButton.disabled = false;
    return;
  }
  if (job.state === "error") throw new Error(job.message);
  window.setTimeout(() => checkJob(jobId).catch(showProcessingError), 800);
}

function showProcessingError(error) {
  statusArea.hidden = false;
  statusArea.classList.add("active", "error");
  statusArea.textContent = error.message || "Something went wrong while processing the video.";
  generateButton.disabled = false;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  setProgress("Uploading and preparing video files", 5);
  generateButton.disabled = true;
  try {
    const response = await fetch("/start-process", { method: "POST", body: new FormData(form) });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Could not start processing.");
    checkJob(data.job_id).catch(showProcessingError);
  } catch (error) {
    showProcessingError(error);
  }
});
