import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import ts from "../frontend/node_modules/typescript/lib/typescript.js";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const source = readFileSync(resolve(root, "frontend/src/lib/clipCopy.ts"), "utf8");
const { outputText } = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.ES2022,
    target: ts.ScriptTarget.ES2022,
  },
});
const moduleUrl = `data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`;
const { buildTranscriptClipCopy, buildTranscriptSnapForRange, clipCopyGapLabels, hasUsefulClipLabel, isClipCopyIncomplete, mergeMissingClipCopyFields } = await import(moduleUrl);

test("transcript snap uses overlapping caption rows", () => {
  assert.deepEqual(
    buildTranscriptSnapForRange(
      [
        { start: 0, end: 5, text: "开场" },
        { start: 5, end: 12, text: "AI 正在进入业务流程" },
        { start: 12, end: 20, text: "团队开始用它处理剪辑" },
      ],
      6,
      18,
    ),
    {
      end: 20,
      label: "2 句字幕",
      quote: "AI 正在进入业务流程 团队开始用它处理剪辑",
      start: 5,
    },
  );
});

test("transcript snap falls back to the nearest caption row", () => {
  assert.deepEqual(
    buildTranscriptSnapForRange(
      [
        { start: 0, end: 4, text: "第一句" },
        { start: 20, end: 24, text: "最近一句" },
      ],
      18,
      19,
    ),
    {
      end: 24,
      label: "1 句字幕",
      quote: "最近一句",
      start: 20,
    },
  );
});

test("transcript snap ignores empty inputs", () => {
  assert.equal(buildTranscriptSnapForRange([], 0, 10), null);
});

test("transcript clip copy builds editable delivery fields", () => {
  assert.deepEqual(
    buildTranscriptClipCopy({
      end: 82,
      label: "2 句字幕",
      quote: "AI agent workflows are moving from demos to operations.",
      start: 65,
    }),
    {
      label: "AI agent workflows are m...",
      note: "字幕选区 01:05 - 01:22 · 2 句字幕",
      quote: "AI agent workflows are moving from demos to operations.",
    },
  );
});

test("transcript clip copy keeps short labels intact and normalizes whitespace for labels", () => {
  assert.deepEqual(
    buildTranscriptClipCopy({
      end: 15,
      label: "1 句字幕",
      quote: "  模型   正在进入真实业务  ",
      start: 4,
    }),
    {
      label: "模型 正在进入真实业务",
      note: "字幕选区 00:04 - 00:15 · 1 句字幕",
      quote: "  模型   正在进入真实业务  ",
    },
  );
});

test("transcript clip copy ignores empty quotes", () => {
  assert.equal(
    buildTranscriptClipCopy({
      end: 15,
      label: "1 句字幕",
      quote: "   ",
      start: 4,
    }),
    null,
  );
});

test("clip copy completeness treats default labels and empty fields as incomplete", () => {
  assert.equal(hasUsefulClipLabel("未命名片段"), false);
  assert.equal(hasUsefulClipLabel("  产品观点  "), true);
  assert.equal(isClipCopyIncomplete({ label: "未命名片段", note: "字幕选区 00:01 - 00:05", quote: "原文" }), true);
  assert.equal(isClipCopyIncomplete({ label: "产品观点", note: "", quote: "原文" }), true);
  assert.equal(isClipCopyIncomplete({ label: "产品观点", note: "字幕选区 00:01 - 00:05", quote: "原文" }), false);
});

test("clip copy gap labels describe every missing delivery field", () => {
  assert.deepEqual(clipCopyGapLabels({ label: "未命名片段", note: "", quote: "" }), ["标题", "备注", "引用"]);
  assert.deepEqual(clipCopyGapLabels({ label: "产品观点", note: "字幕选区 00:01 - 00:05", quote: "" }), ["引用"]);
  assert.deepEqual(clipCopyGapLabels({ label: "产品观点", note: "字幕选区 00:01 - 00:05", quote: "原文" }), []);
});

test("clip copy merge fills only missing delivery fields", () => {
  assert.deepEqual(
    mergeMissingClipCopyFields(
      { label: "手写标题", note: "手写备注", quote: "" },
      {
        label: "字幕标题",
        note: "字幕选区 00:01 - 00:05 · 1 句字幕",
        quote: "字幕原文",
      },
    ),
    {
      label: "手写标题",
      note: "手写备注",
      quote: "字幕原文",
    },
  );
});

test("clip copy merge replaces default labels without overwriting useful fields", () => {
  assert.deepEqual(
    mergeMissingClipCopyFields(
      { label: "未命名片段", note: "已有备注", quote: "" },
      {
        label: "字幕标题",
        note: "字幕选区 00:01 - 00:05 · 1 句字幕",
        quote: "字幕原文",
      },
    ),
    {
      label: "字幕标题",
      note: "已有备注",
      quote: "字幕原文",
    },
  );
});

test("clip copy merge skips complete fields or missing generated copy", () => {
  assert.equal(
    mergeMissingClipCopyFields({ label: "手写标题", note: "手写备注", quote: "手写引用" }, {
      label: "字幕标题",
      note: "字幕选区 00:01 - 00:05 · 1 句字幕",
      quote: "字幕原文",
    }),
    null,
  );
  assert.equal(mergeMissingClipCopyFields({ label: "未命名片段", note: "", quote: "" }, null), null);
});
