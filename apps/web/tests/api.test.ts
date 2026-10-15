import test from "node:test";
import assert from "node:assert/strict";
import { request } from "../src/lib/api.ts";

test("user cancellation keeps a separate bounded timeout signal", async () => {
  const controller = new AbortController();
  await request(
    "/health",
    { signal: controller.signal },
    async (_input, init) => {
      assert.notEqual(init?.signal, controller.signal);
      controller.abort();
      assert.equal(init?.signal?.aborted, true);
      return Response.json({ ok: true });
    },
  );
});

test("structured validation errors surface useful messages", async () => {
  const fetcher: typeof fetch = async () =>
    new Response(
      JSON.stringify({
        detail: [{ loc: ["body", "control_time"], msg: "Offset required" }],
      }),
      { status: 422 },
    );
  await assert.rejects(
    request("/api/v1/digest", {}, fetcher),
    /control_time.*Offset required/,
  );
});
test("unavailable and non-JSON API responses have readable errors", async () => {
  await assert.rejects(
    request("/health", {}, async () => {
      throw new TypeError("failed");
    }),
    /соедин/,
  );
  await assert.rejects(
    request(
      "/health",
      {},
      async () => new Response("<html>oops</html>", { status: 502 }),
    ),
    /502/,
  );
});
test("successful responses are parsed and no secret headers added", async () => {
  let observed: RequestInit | undefined;
  const value = await request<{ ok: boolean }>(
    "/health",
    {},
    async (_input, init) => {
      observed = init;
      return Response.json({ ok: true });
    },
  );
  assert.equal(value.ok, true);
  assert.equal(new Headers(observed?.headers).has("authorization"), false);
});
