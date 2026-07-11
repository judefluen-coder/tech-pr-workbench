import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import ts from "../frontend/node_modules/typescript/lib/typescript.js";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
globalThis.window = globalThis;

async function importTypescriptModule(path) {
  const source = readFileSync(resolve(root, path), "utf8");
  const { outputText } = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022 },
  });
  return import(`data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`);
}

const { demoApi } = await importTypescriptModule("frontend/src/lib/demoApi.ts");

test("demo API supports the discovery, processing, editing, and export path", async () => {
  const report = await demoApi.daily({ start_date: "2026-07-01", end_date: "2026-07-01" });
  assert.equal(report.items.length, 3);
  assert.equal(report.source_runs.length, 4);
  assert.equal(report.items[1].id, 1002);

  const initial = await demoApi.clipPayload(1002);
  assert.equal(initial.transcripts.length, 48);
  assert.equal(initial.clip_marks.length, 3);

  const created = await demoApi.createClip({
    video_id: 1002,
    start_seconds: 136,
    end_seconds: 148,
    label: "体验新增片段",
    note: "浏览器内存",
    quote: "体验版不会修改本地数据库。",
    status: "ready",
  });
  const updated = await demoApi.updateClip(created.id, { ...created, label: "体验修改片段", status: "approved" });
  assert.equal(updated.label, "体验修改片段");

  const afterCreate = await demoApi.clipPayload(1002);
  const reversedIds = afterCreate.clip_marks.map((clip) => clip.id).reverse();
  const reordered = await demoApi.reorderClips(1002, reversedIds);
  assert.deepEqual(reordered.clip_marks.map((clip) => clip.id), reversedIds);

  await demoApi.deleteClip(created.id);
  assert.equal((await demoApi.clipPayload(1002)).clip_marks.length, 3);

  const downloadJob = await demoApi.downloadTranslate(1001);
  assert.equal((await demoApi.job(downloadJob.id)).status, "running");
  assert.equal((await demoApi.job(downloadJob.id)).status, "completed");
  assert.equal((await demoApi.clipPayload(1001)).transcripts.length, 48);

  const renderJob = await demoApi.renderClips(1002, {});
  await demoApi.job(renderJob.id);
  const completedRender = await demoApi.job(renderJob.id);
  assert.equal(completedRender.status, "completed");
  assert.equal(JSON.parse(completedRender.result).output_width, 1920);
});
