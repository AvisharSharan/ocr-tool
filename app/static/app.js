const fileInput = document.querySelector("#file");
const preprocessInput = document.querySelector("#preprocess");
const runOcrButton = document.querySelector("#runOcr");
const ocrText = document.querySelector("#ocrText");
const chatHistoryEl = document.querySelector("#chatHistory");
const statusBadge = document.querySelector("#status");
const questionInput = document.querySelector("#question");
const chatForm = document.querySelector("#chatForm");
const clearChatButton = document.querySelector("#clearChat");
const chatHistory = [];

function setStatus(message, error = false) {
  statusBadge.textContent = message;
  statusBadge.classList.toggle("error", error);
}

async function postJson(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || "Request failed");
  }
  return data;
}

function addMessage(role, content) {
  const message = { role, content };
  chatHistory.push(message);

  const node = document.createElement("div");
  node.className = `message ${role}`;

  const label = document.createElement("span");
  label.className = "message-label";
  label.textContent = role === "user" ? "You" : "Gemma";

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  if (role === "assistant") {
    bubble.innerHTML = renderMarkdown(content);
  } else {
    bubble.textContent = content;
  }

  node.append(label, bubble);
  chatHistoryEl.appendChild(node);
  chatHistoryEl.scrollTop = chatHistoryEl.scrollHeight;
}

function renderMarkdown(markdown) {
  const blocks = [];
  let text = escapeHtml(markdown);

  text = text.replace(/```([\s\S]*?)```/g, (_, code) => {
    const key = `\u0000CODE${blocks.length}\u0000`;
    blocks.push(`<pre><code>${code.trim()}</code></pre>`);
    return key;
  });

  text = text
    .replace(/^### (.*)$/gm, "<h4>$1</h4>")
    .replace(/^## (.*)$/gm, "<h3>$1</h3>")
    .replace(/^# (.*)$/gm, "<h2>$1</h2>")
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.+?)\*/g, "<em>$1</em>")
    .replace(/`([^`]+)`/g, "<code>$1</code>");

  text = renderLists(text);
  text = text.replace(/\n{2,}/g, "</p><p>").replace(/\n/g, "<br>");
  text = `<p>${text}</p>`;

  blocks.forEach((block, index) => {
    text = text.replace(`\u0000CODE${index}\u0000`, block);
  });

  return text.replace(/<p><\/p>/g, "");
}

function renderLists(text) {
  const lines = text.split("\n");
  const output = [];
  let inList = false;

  for (const line of lines) {
    const match = line.match(/^\s*[-*]\s+(.+)$/);
    if (match) {
      if (!inList) {
        output.push("<ul>");
        inList = true;
      }
      output.push(`<li>${match[1]}</li>`);
      continue;
    }

    if (inList) {
      output.push("</ul>");
      inList = false;
    }
    output.push(line);
  }

  if (inList) output.push("</ul>");
  return output.join("\n");
}

function escapeHtml(value) {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function formatPayload(data) {
  if (typeof data.text === "string") return data.text;
  if (typeof data.summary === "string") return data.summary;
  if (typeof data.answer === "string") return data.answer;
  return JSON.stringify(data, null, 2);
}

runOcrButton.addEventListener("click", async () => {
  const file = fileInput.files[0];
  if (!file) {
    setStatus("Pick a file", true);
    return;
  }

  const form = new FormData();
  form.append("file", file);
  form.append("preprocess", preprocessInput.checked ? "true" : "false");

  setStatus("Running OCR");
  runOcrButton.disabled = true;
  try {
    const response = await fetch("/api/ocr", { method: "POST", body: form });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "OCR failed");
    ocrText.value = data.text || "";
    addMessage("assistant", `OCR complete: ${data.filename}, ${data.page_count} page(s).`);
    setStatus("OCR done");
  } catch (error) {
    setStatus("OCR error", true);
    addMessage("assistant", error.message);
  } finally {
    runOcrButton.disabled = false;
  }
});

document.querySelector("#copyText").addEventListener("click", async () => {
  await navigator.clipboard.writeText(ocrText.value);
  setStatus("Copied");
});

document.querySelectorAll("[data-action]").forEach((button) => {
  button.addEventListener("click", async () => {
    if (!ocrText.value.trim()) {
      setStatus("No text", true);
      return;
    }

    const action = button.dataset.action;
    addMessage("user", button.textContent);
    setStatus("AI running");
    button.disabled = true;
    try {
      const data = await postJson(`/api/ai/${action}`, { text: ocrText.value });
      addMessage("assistant", formatPayload(data));
      setStatus("AI done");
    } catch (error) {
      setStatus("AI error", true);
      addMessage("assistant", error.message);
    } finally {
      button.disabled = false;
    }
  });
});

chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!ocrText.value.trim() || !questionInput.value.trim()) {
    setStatus("Need text/question", true);
    return;
  }

  const question = questionInput.value.trim();
  addMessage("user", question);
  questionInput.value = "";
  setStatus("AI running");
  try {
    const data = await postJson("/api/ai/ask", {
      text: ocrText.value,
      question,
      history: chatHistory.slice(-8),
    });
    addMessage("assistant", data.answer);
    setStatus("AI done");
  } catch (error) {
    setStatus("AI error", true);
    addMessage("assistant", error.message);
  }
});

clearChatButton.addEventListener("click", () => {
  chatHistory.length = 0;
  chatHistoryEl.replaceChildren();
  setStatus("Chat cleared");
});
