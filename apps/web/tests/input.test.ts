import test from "node:test";
import assert from "node:assert/strict";
import {
  parseArticles,
  controlTime,
  safeUrl,
  journalCsv,
} from "../src/lib/input.ts";

test("JSON retains missing values as null and rejects wrong shape", () => {
  assert.equal(
    parseArticles('[{"title":"Факт"}]', "json")[0].published_at,
    null,
  );
  assert.equal(
    parseArticles('[{"text":"  факт\\n"}]', "json")[0].text,
    "  факт\n",
  );
  assert.throws(() => parseArticles('{"title":"Факт"}', "json"), /массив/);
  assert.throws(() => parseArticles("[42]", "json"), /объект/);
});
test("CSV preserves quoted commas, escaped quotes and multiline text", () => {
  const rows = parseArticles(
    'id,title,text,published_at\r\n1,"Атака, обновление","Факт ""цитата""\nстрока",2026-10-14T10:00:00+03:00',
    "csv",
  );
  assert.equal(rows[0].title, "Атака, обновление");
  assert.equal(rows[0].text, 'Факт "цитата"\nстрока');
  assert.throws(() => parseArticles('title,text\n"broken', "csv"), /кавычк/);
});
test("Moscow control time is explicit and invalid dates rejected", () => {
  assert.equal(controlTime("2026-10-14", "12:30"), "2026-10-14T12:30:00+03:00");
  assert.throws(() => controlTime("2026-02-30", "12:30"), /дат/);
  assert.throws(() => controlTime("2026-10-14", "24:00"), /время/);
});
test("unsafe links disabled and spreadsheet formula cells escaped", () => {
  assert.equal(safeUrl("javascript:alert(1)"), null);
  assert.equal(
    safeUrl("https://example.org/story"),
    "https://example.org/story",
  );
  assert.match(journalCsv([{ title: '=HYPERLINK("evil")' }]), /'=/);
});
