import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import ts from "../frontend/node_modules/typescript/lib/typescript.js";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const source = readFileSync(resolve(root, "frontend/src/lib/clipValidation.ts"), "utf8");
const { outputText } = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.ES2022,
    target: ts.ScriptTarget.ES2022,
  },
});
const moduleUrl = `data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`;
const { buildManualClipValidation } = await import(moduleUrl);

test("manual clip validation accepts a valid range", () => {
  assert.deepEqual(
    buildManualClipValidation({
      duplicate: false,
      end: 15,
      start: 0,
      timelineDuration: 60,
    }),
    { ok: true, severity: "ready", message: "片段时长 0:15，可以加入序列。" },
  );
});

test("manual clip validation supports edit-ready copy", () => {
  assert.deepEqual(
    buildManualClipValidation({
      duplicate: false,
      end: 15,
      readyAction: "可以保存",
      start: 0,
      timelineDuration: 60,
    }),
    { ok: true, severity: "ready", message: "片段时长 0:15，可以保存。" },
  );
});

test("manual clip validation blocks invalid ranges", () => {
  assert.equal(
    buildManualClipValidation({
      duplicate: false,
      end: 5,
      start: 10,
      timelineDuration: 60,
    }).message,
    "出点必须晚于入点。",
  );
  assert.equal(
    buildManualClipValidation({
      duplicate: false,
      end: 90,
      start: 10,
      timelineDuration: 60,
    }).message,
    "出点不能超过素材时长 01:00。",
  );
});

test("manual clip validation blocks duplicate ranges", () => {
  assert.deepEqual(
    buildManualClipValidation({
      duplicate: true,
      end: 31,
      start: 8.5,
      timelineDuration: 420,
    }),
    { ok: false, severity: "block", message: "这个选区已经在剪辑序列里。" },
  );
});
