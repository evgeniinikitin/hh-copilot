const HHApi = (() => {
  const BASE_URL = "http://127.0.0.1:8765";

  async function request(path, options = {}) {
    const response = await fetch(`${BASE_URL}${path}`, {
      ...options,
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    });
    if (!response.ok) {
      const detail = await response.text();
      throw new Error(`Backend ${response.status}: ${detail.slice(0, 300)}`);
    }
    return response.json();
  }

  return {
    health: () => request("/health"),
    status: () => request("/api/v1/status"),
    addVacancy: (vacancyId) =>
      request("/api/v1/vacancies", {
        method: "POST",
        body: JSON.stringify({ vacancy_id: vacancyId, source: "instant" }),
      }),
    sync: (vacancyIds) =>
      request("/api/v1/sync", {
        method: "POST",
        body: JSON.stringify({ vacancy_ids: vacancyIds, source: "chrome_sync" }),
      }),
    processBaseline: (limit) =>
      request("/api/v1/process-baseline", {
        method: "POST",
        body: JSON.stringify({ limit }),
      }),
  };
})();
