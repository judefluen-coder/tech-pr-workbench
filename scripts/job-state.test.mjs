import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import ts from "../frontend/node_modules/typescript/lib/typescript.js";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const source = readFileSync(resolve(root, "frontend/src/lib/jobState.ts"), "utf8");
const { outputText } = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.ES2022,
    target: ts.ScriptTarget.ES2022,
  },
});
const moduleUrl = `data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`;
const { buildJobState, isActiveJobStatus, jobResult, jobVideoId } = await import(moduleUrl);

function makeJob(id, status, videoId, result = "{}") {
  return {
    attempts: status === "running" ? 1 : 0,
    created_at: "2026-07-11T00:00:00Z",
    id,
    message: "test",
    payload: JSON.stringify({ video_id: videoId }),
    progress: 0,
    result,
    status,
    type: "render_clips",
    updated_at: "2026-07-11T00:00:00Z",
  };
}

test("job state selects the newest and newest active job per video", () => {
  const completed = makeJob(10, "completed", 7);
  const running = makeJob(12, "running", 7);
  const olderQueued = makeJob(11, "queued", 7);
  const other = makeJob(13, "failed", 8);

  assert.deepEqual(buildJobState([completed, other, olderQueued, running]), {
    jobs: { 10: completed, 11: olderQueued, 12: running, 13: other },
    activeJobIdsByVideo: { 7: 12 },
    latestJobIdsByVideo: { 7: 12, 8: 13 },
  });
});

test("job payload and result parsing tolerate malformed persisted data", () => {
  assert.equal(jobVideoId(makeJob(1, "queued", 5)), 5);
  assert.equal(jobVideoId({ payload: "not-json" }), null);
  assert.deepEqual(jobResult(makeJob(2, "completed", 5, '{"sequence_path":"/tmp/clip.mp4"}')), { sequence_path: "/tmp/clip.mp4" });
  assert.equal(jobResult({ result: "[]" }), null);
  assert.equal(jobResult({ result: "not-json" }), null);
});

test("only queued and running jobs are active", () => {
  assert.equal(isActiveJobStatus("queued"), true);
  assert.equal(isActiveJobStatus("running"), true);
  assert.equal(isActiveJobStatus("completed"), false);
  assert.equal(isActiveJobStatus("failed"), false);
});
