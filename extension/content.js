(() => {
  const SYNC_COOLDOWN_MS = 120_000;
  const LAST_SYNC_KEY = "hhCopilotLastSyncAt";
  const FALLBACK_OPENED_KEY = "hhCopilotFallbackOpenedAt";
  let syncInProgress = false;

  function background(message) {
    return new Promise((resolve, reject) => {
      chrome.runtime.sendMessage(message, (response) => {
        if (chrome.runtime.lastError) return reject(chrome.runtime.lastError);
        if (response && response.error) return reject(new Error(response.error));
        resolve(response);
      });
    });
  }

  async function fetchFavoritesPage(url) {
    const response = await fetch(url, { credentials: "include", redirect: "follow" });
    if (!response.ok || !HHUtils.isFavoritesUrl(response.url)) return null;
    const html = await response.text();
    const parsed = new DOMParser().parseFromString(html, "text/html");
    const text = parsed.body ? parsed.body.textContent : "";
    if (!/избран|favorite|favourite/i.test(`${response.url} ${text}`)) return null;
    return { document: parsed, finalUrl: response.url };
  }

  async function collectViaAuthenticatedFetch() {
    for (const url of HHUtils.candidateFavoritesUrls()) {
      try {
        const first = await fetchFavoritesPage(url);
        if (!first) continue;
        const ids = new Set(HHUtils.extractFavoriteVacancyIds(first.document));
        const pageLinks = [...first.document.querySelectorAll("a[href]")]
          .map((link) => link.href)
          .filter((href) => HHUtils.isFavoritesUrl(href) && /[?&]page=\d+/i.test(href));
        for (const pageUrl of [...new Set(pageLinks)].slice(0, 49)) {
          const page = await fetchFavoritesPage(pageUrl);
          if (page) {
            HHUtils.extractFavoriteVacancyIds(page.document).forEach((id) => ids.add(id));
          }
        }
        return { ids: [...ids], favoritesUrl: first.finalUrl };
      } catch (error) {
        console.warn("HH Copilot favorites fetch failed", url, error);
      }
    }
    return null;
  }

  async function waitForFavoritesDom() {
    const deadline = Date.now() + 12_000;
    while (Date.now() < deadline) {
      const ids = HHUtils.extractFavoriteVacancyIds(document);
      if (ids.length) return ids;
      const bodyText = document.body ? document.body.textContent : "";
      if (/нет избранных вакансий|в избранном пока нет|nothing.*favorites/i.test(bodyText)) {
        return [];
      }
      await new Promise((resolve) => setTimeout(resolve, 400));
    }
    throw new Error("Страница избранного не успела загрузить вакансии");
  }

  async function performSync({ force = false } = {}) {
    if (syncInProgress) return { skipped: "already-running" };
    syncInProgress = true;
    try {
      const stored = await chrome.storage.local.get(LAST_SYNC_KEY);
      const lastSync = Number(stored[LAST_SYNC_KEY] || 0);
      if (!force && Date.now() - lastSync < SYNC_COOLDOWN_MS) return { skipped: "cooldown" };

      if (HHUtils.isFavoritesUrl(location.href)) {
        const domIds = await waitForFavoritesDom();
        const fetchedFromPages = await collectViaAuthenticatedFetch();
        const allIds = new Set(domIds);
        if (fetchedFromPages) fetchedFromPages.ids.forEach((id) => allIds.add(id));
        const result = await background({ type: "API_SYNC", vacancyIds: [...allIds] });
        await chrome.storage.local.set({ [LAST_SYNC_KEY]: Date.now() });
        await chrome.storage.local.remove(FALLBACK_OPENED_KEY);
        return result;
      }

      const fetched = await collectViaAuthenticatedFetch();
      if (fetched && fetched.ids.length) {
        const result = await background({ type: "API_SYNC", vacancyIds: fetched.ids });
        await chrome.storage.local.set({ [LAST_SYNC_KEY]: Date.now() });
        await chrome.storage.local.remove(FALLBACK_OPENED_KEY);
        return result;
      }

      const favoritesUrl =
        (fetched && fetched.favoritesUrl) ||
        HHUtils.findFavoritesUrl(document) ||
        `${location.origin}${HHUtils.FAVORITES_PATHS[0]}`;
      const fallbackState = await chrome.storage.local.get(FALLBACK_OPENED_KEY);
      const fallbackOpenedAt = Number(fallbackState[FALLBACK_OPENED_KEY] || 0);
      if (Date.now() - fallbackOpenedAt < SYNC_COOLDOWN_MS) {
        throw new Error("Не удалось прочитать избранное; откройте его страницу вручную");
      }
      await chrome.storage.local.set({ [FALLBACK_OPENED_KEY]: Date.now() });
      await background({ type: "OPEN_FAVORITES_TAB", url: favoritesUrl });
      return { fallback: "background-tab" };
    } finally {
      syncInProgress = false;
    }
  }

  document.addEventListener(
    "click",
    (event) => {
      const intent = HHUtils.toggleIntent(event.target);
      if (!intent || intent.adding === false) return;
      const vacancyId = HHUtils.vacancyIdNear(intent.button);
      if (!vacancyId) return;
      if (intent.adding === true) {
        setTimeout(() => {
          const confirmed = HHUtils.toggleIntent(intent.button);
          const pressed = intent.button.getAttribute("aria-pressed");
          if ((confirmed && confirmed.adding === false) || pressed === "true") {
            background({ type: "API_ADD_VACANCY", vacancyId }).catch((error) =>
              console.warn("HH Copilot instant mode failed", error)
            );
          }
        }, 350);
      }
    },
    true
  );

  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (message.type !== "HH_AUTO_SYNC" && message.type !== "HH_MANUAL_SYNC") return false;
    performSync({ force: message.type === "HH_MANUAL_SYNC" })
      .then(sendResponse)
      .catch((error) => sendResponse({ error: error.message }));
    return true;
  });

  performSync().catch((error) => console.warn("HH Copilot auto sync failed", error));
})();
