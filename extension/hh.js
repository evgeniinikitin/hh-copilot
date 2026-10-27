globalThis.HHUtils = (() => {
  const VACANCY_PATTERN = /(?:https?:\/\/(?:[a-z0-9-]+\.)?hh\.ru)?\/vacancy\/(\d+)/i;
  const FAVORITES_PATHS = [
    "/applicant/favorite-vacancies",
    "/applicant/favorite_vacancies",
    "/applicant/vacancies/favorites",
    "/applicant/favorites",
  ];

  function extractVacancyId(value) {
    const match = String(value || "").match(VACANCY_PATTERN);
    return match ? match[1] : null;
  }

  function isFavoritesUrl(value) {
    return /favorite|favourite|избран/i.test(String(value || ""));
  }

  function findFavoritesUrl(root = document) {
    const anchors = [...root.querySelectorAll("a[href]")];
    const link = anchors.find((anchor) => {
      const haystack = [
        anchor.href,
        anchor.textContent,
        anchor.getAttribute("aria-label"),
        anchor.getAttribute("data-qa"),
      ]
        .filter(Boolean)
        .join(" ");
      return /favorite|favourite|избран/i.test(haystack) && /vacan/i.test(haystack);
    });
    return link ? link.href : null;
  }

  function extractVacancyIds(root) {
    const ids = new Set();
    const cards = root.querySelectorAll(
      "[data-qa*='vacancy-serp__vacancy'], [data-qa*='vacancy-card'], [data-vacancy-id]"
    );
    const scope = cards.length ? cards : root.querySelectorAll("a[href*='/vacancy/']");
    for (const node of scope) {
      const explicit = node.getAttribute && node.getAttribute("data-vacancy-id");
      if (explicit && /^\d+$/.test(explicit)) ids.add(explicit);
      const links = node.matches && node.matches("a[href]") ? [node] : node.querySelectorAll("a[href]");
      for (const link of links) {
        const id = extractVacancyId(link.href || link.getAttribute("href"));
        if (id) ids.add(id);
      }
    }
    return [...ids];
  }

  function favoriteButtonState(label, pressed) {
    const normalized = String(label || "").toLowerCase();
    if (pressed === "true") return "saved";
    if (pressed === "false") return "unsaved";
    if (/удал|убрат|remove|в избранном|добавлен[^\s]*\s+в\s+избран|favorited|saved/.test(normalized)) {
      return "saved";
    }
    if (/добав|\badd\b|сохран|\bsave\b/.test(normalized)) return "unsaved";
    return null;
  }

  function extractFavoriteVacancyIds(root) {
    const ids = new Set();
    const candidates = root.querySelectorAll(
      "[data-qa*='vacancy-serp__vacancy'], [data-qa*='vacancy-card'], [data-vacancy-id]"
    );
    for (const card of candidates) {
      if (card.matches && card.matches("button, [role='button']")) continue;
      const links = card.querySelectorAll ? card.querySelectorAll("a[href*='/vacancy/']") : [];
      if (!links.length) continue;

      const controls = card.querySelectorAll
        ? card.querySelectorAll(
            "button, [role='button'], [data-qa*='favorite'], [data-qa*='favourite']"
          )
        : [];
      const explicitlySaved = [...controls].some((control) => {
        const intent = toggleIntent(control);
        return intent && intent.adding === false;
      });
      if (!explicitlySaved) continue;

      const explicit = card.getAttribute && card.getAttribute("data-vacancy-id");
      if (explicit && /^\d+$/.test(explicit)) ids.add(explicit);
      for (const link of links) {
        const id = extractVacancyId(link.href || link.getAttribute("href"));
        if (id) ids.add(id);
      }
    }
    return [...ids];
  }

  function candidateFavoritesUrls(root = document) {
    const discovered = findFavoritesUrl(root);
    const origin = location.origin;
    return [...new Set([discovered, ...FAVORITES_PATHS.map((path) => `${origin}${path}`)].filter(Boolean))];
  }

  function toggleIntent(target) {
    const element = target instanceof Element ? target : target && target.parentElement;
    if (!element) return null;
    const button = element.closest(
      "button, [role='button'], [data-qa*='favorite'], [data-qa*='favourite']"
    );
    if (!button) return null;
    const label = [
      button.getAttribute("aria-label"),
      button.getAttribute("title"),
      button.getAttribute("data-qa"),
      button.textContent,
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    if (!/favorite|favourite|избран|отобран|сохран|\bsave\b/.test(label)) return null;
    const state = favoriteButtonState(label, button.getAttribute("aria-pressed"));
    return { button, adding: state === null ? null : state === "unsaved" };
  }

  function vacancyIdNear(node) {
    let current = node instanceof Element ? node : node && node.parentElement;

    // HH puts "vacancy" in the favourite button's own data-qa attribute. A
    // generic closest("[data-qa*='vacancy']") therefore stops on the button,
    // before reaching the card that contains the vacancy link. Walk upwards
    // until the smallest ancestor with exactly one vacancy link is found.
    for (let depth = 0; current && depth < 12; depth += 1) {
      const explicit = current.getAttribute && current.getAttribute("data-vacancy-id");
      if (explicit && /^\d+$/.test(explicit)) return explicit;

      if (current.matches && current.matches("a[href*='/vacancy/']")) {
        const ownId = extractVacancyId(current.href || current.getAttribute("href"));
        if (ownId) return ownId;
      }

      const links = current.querySelectorAll
        ? current.querySelectorAll("a[href*='/vacancy/']")
        : [];
      if (links.length === 1) {
        const id = extractVacancyId(links[0].href || links[0].getAttribute("href"));
        if (id) return id;
      }
      current = current.parentElement;
    }

    return extractVacancyId(location.href);
  }

  return {
    FAVORITES_PATHS,
    candidateFavoritesUrls,
    extractFavoriteVacancyIds,
    extractVacancyId,
    extractVacancyIds,
    favoriteButtonState,
    findFavoritesUrl,
    isFavoritesUrl,
    toggleIntent,
    vacancyIdNear,
  };
})();
