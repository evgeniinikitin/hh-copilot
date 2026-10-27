importScripts("api.js");

async function updateBadge() {
  try {
    const status = await HHApi.status();
    const remaining = status.queue_size + status.processing;
    await chrome.action.setBadgeBackgroundColor({ color: "#2563EB" });
    await chrome.action.setBadgeText({ text: remaining ? String(Math.min(remaining, 99)) : "" });
  } catch (_error) {
    await chrome.action.setBadgeText({ text: "" });
  }
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  const run = async () => {
    switch (message.type) {
      case "API_HEALTH":
        return HHApi.health();
      case "API_STATUS":
        return HHApi.status();
      case "API_ADD_VACANCY": {
        const result = await HHApi.addVacancy(message.vacancyId);
        await updateBadge();
        return result;
      }
      case "API_SYNC": {
        const result = await HHApi.sync(message.vacancyIds);
        await updateBadge();
        return result;
      }
      case "API_PROCESS_BASELINE": {
        const result = await HHApi.processBaseline(message.limit);
        await updateBadge();
        return result;
      }
      case "OPEN_FAVORITES_TAB": {
        const tab = await chrome.tabs.create({ url: message.url, active: false });
        return { tabId: tab.id };
      }
      default:
        throw new Error(`Unknown message: ${message.type}`);
    }
  };
  run().then(sendResponse).catch((error) => sendResponse({ error: error.message }));
  return true;
});

chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status !== "complete" || !tab.url || !/^https:\/\/([a-z0-9-]+\.)?hh\.ru\//i.test(tab.url)) {
    return;
  }
  chrome.tabs.sendMessage(tabId, { type: "HH_AUTO_SYNC" }).catch(() => {});
});

chrome.runtime.onStartup.addListener(updateBadge);
chrome.runtime.onInstalled.addListener(updateBadge);
