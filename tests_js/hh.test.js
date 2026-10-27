const test = require("node:test");
const assert = require("node:assert/strict");

globalThis.Element = class {};
require("../extension/hh.js");

const { extractFavoriteVacancyIds, favoriteButtonState } = globalThis.HHUtils;

function card(vacancyId, stateLabel) {
  const button = new Element();
  button.textContent = "";
  button.closest = () => button;
  button.getAttribute = (name) => (name === "aria-label" ? stateLabel : null);
  const link = {
    href: `https://hh.ru/vacancy/${vacancyId}`,
    getAttribute: () => `/vacancy/${vacancyId}`,
  };
  const result = new Element();
  result.matches = () => false;
  result.getAttribute = (name) => (name === "data-vacancy-id" ? vacancyId : null);
  result.querySelectorAll = (selector) =>
    selector.startsWith("a[") ? [link] : [button];
  return result;
}

test("recognizes an explicitly saved vacancy", () => {
  assert.equal(favoriteButtonState("Убрать из избранного", null), "saved");
  assert.equal(favoriteButtonState("Добавлено в избранное", null), "saved");
  assert.equal(favoriteButtonState("Remove from favorites", null), "saved");
  assert.equal(favoriteButtonState("", "true"), "saved");
  assert.equal(favoriteButtonState("Добавить в избранное", "true"), "saved");
});

test("rejects recommendation cards that are not saved", () => {
  assert.equal(favoriteButtonState("Добавить в избранное", null), "unsaved");
  assert.equal(favoriteButtonState("Save vacancy", null), "unsaved");
  assert.equal(favoriteButtonState("", "false"), "unsaved");
});

test("fails closed when favorite state is unknown", () => {
  assert.equal(favoriteButtonState("Vacancy actions", null), null);
});

test("extracts saved cards and skips recommendations", () => {
  const root = {
    querySelectorAll: () => [
      card("111", "Убрать из избранного"),
      card("222", "Добавить в избранное"),
      card("333", "Vacancy actions"),
    ],
  };

  assert.deepEqual(extractFavoriteVacancyIds(root), ["111"]);
});
