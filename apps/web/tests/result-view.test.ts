import test from "node:test";
import assert from "node:assert/strict";
import { selectResultView } from "../src/lib/result-view.ts";

const session = { digest_id: "previous", digest_text: "Old digest" };
test("a requested ID never renders a different saved result while loading or failing", () => {
  assert.deepEqual(selectResultView(session, "requested", null), {
    status: "loading",
  });
  assert.deepEqual(
    selectResultView(session, "requested", {
      id: "requested",
      status: "error",
      error: "Not found",
    }),
    { status: "error", error: "Not found" },
  );
  assert.deepEqual(
    selectResultView(session, "requested", {
      id: "previous",
      status: "ready",
      result: session,
    }),
    { status: "loading" },
  );
});
test("successful request must match requested identity; ordinary route restores session", () => {
  const requested = { digest_id: "requested", digest_text: "New digest" };
  assert.deepEqual(
    selectResultView(session, "requested", {
      id: "requested",
      status: "ready",
      result: requested,
    }),
    { status: "ready", result: requested },
  );
  assert.equal(
    selectResultView(session, "requested", {
      id: "requested",
      status: "ready",
      result: session,
    }).status,
    "error",
  );
  assert.deepEqual(selectResultView(session, null, null), {
    status: "ready",
    result: session,
  });
  assert.deepEqual(selectResultView(null, null, null), { status: "empty" });
});
