const form = document.querySelector("#splice-form");
const timestampField = document.querySelector("#timestamp-field");
const timestampInput = document.querySelector("#timestamp");
const statusArea = document.querySelector("#status-area");
const generateButton = document.querySelector("#generate-button");
const placementInputs = document.querySelectorAll("input[name='placement']");

function updateTimestampVisibility() {
  const selectedPlacement = document.querySelector("input[name='placement']:checked")?.value;
  const shouldShow = selectedPlacement === "custom";
  timestampField.hidden = !shouldShow;
  timestampInput.required = shouldShow;
  if (!shouldShow) {
    timestampInput.value = "";
  }
}

placementInputs.forEach((input) => {
  input.addEventListener("change", updateTimestampVisibility);
});

form.addEventListener("submit", () => {
  statusArea.textContent = "Processing video. This may take a little while depending on file size.";
  statusArea.classList.add("active");
  generateButton.disabled = true;
});

updateTimestampVisibility();
