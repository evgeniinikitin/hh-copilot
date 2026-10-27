function send(message) {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage(message, (response) => {
      if (chrome.runtime.lastError) return reject(chrome.runtime.lastError);
      if (response && response.error) return reject(new Error(response.error));
      resolve(response);
    });
  });
}

function formatTime(value) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("ru", { hour: "2-digit", minute: "2-digit" }).format(new Date(value));
}

async function waitForTabReady(tabId) {
  for (let attempt = 0; attempt < 50; attempt += 1) {
    const tab = await chrome.tabs.get(tabId);
    if (tab.status === "complete") return;
    await new Promise((resolve) => setTimeout(resolve, 200));
  }
  throw new Error("Страница HH не успела загрузиться");
}

async function sendToContentScript(tabId, message) {
  await waitForTabReady(tabId);
  try {
    return await chrome.tabs.sendMessage(tabId, message);
  } catch (error) {
    if (!String(error.message).includes("Receiving end does not exist")) throw error;
    await chrome.scripting.executeScript({
      target: { tabId },
      files: ["hh.js", "content.js"],
    });
    return chrome.tabs.sendMessage(tabId, message);
  }
}

async function refresh() {
  const dot = document.querySelector("#backend-dot");
  try {
    await send({ type: "API_HEALTH" });
    const status = await send({ type: "API_STATUS" });
    dot.className = "dot online";
    document.querySelector("#backend").textContent = "Backend работает";
    document.querySelector("#last-sync").textContent = formatTime(status.last_sync_at);
    document.querySelector("#known").textContent = status.known_total;
    document.querySelector("#processed").textContent = status.processed_total;
    document.querySelector("#queue").textContent = status.queue_size + status.processing;
  } catch (_error) {
    dot.className = "dot offline";
    document.querySelector("#backend").textContent = "Backend недоступен";
  }
}

async function activeHHTab() {
  const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
  return tabs.find((tab) => /^https:\/\/([a-z0-9-]+\.)?hh\.ru\//i.test(tab.url || ""));
}

document.querySelector("#sync").addEventListener("click", async (event) => {
  const button = event.currentTarget;
  const message = document.querySelector("#message");
  button.disabled = true;
  message.textContent = "Синхронизирую…";
  try {
    let tab = await activeHHTab();
    if (!tab) tab = await chrome.tabs.create({ url: "https://hh.ru/", active: true });
    const result = await sendToContentScript(tab.id, { type: "HH_MANUAL_SYNC" });
    if (result && result.error) throw new Error(result.error);
    message.textContent = result && result.fallback
      ? "Открыта фоновая вкладка избранного"
      : `Готово: новых ${result.new || 0}, в очереди ${result.queued || 0}`;
    await refresh();
  } catch (error) {
    message.textContent = `Ошибка: ${error.message}`;
  } finally {
    button.disabled = false;
  }
});

document.querySelectorAll("[data-limit]").forEach((button) => {
  button.addEventListener("click", async () => {
    const message = document.querySelector("#message");
    button.disabled = true;
    try {
      const result = await send({ type: "API_PROCESS_BASELINE", limit: Number(button.dataset.limit) });
      message.textContent = `Добавлено в очередь: ${result.queued}`;
      await refresh();
    } catch (error) {
      message.textContent = `Ошибка: ${error.message}`;
    } finally {
      button.disabled = false;
    }
  });
});

refresh();
