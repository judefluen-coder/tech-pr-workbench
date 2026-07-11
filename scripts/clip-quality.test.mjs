import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import ts from "../frontend/node_modules/typescript/lib/typescript.js";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const source = readFileSync(resolve(root, "frontend/src/lib/clipQuality.ts"), "utf8");
const { outputText } = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.ES2022,
    target: ts.ScriptTarget.ES2022,
  },
});
const moduleUrl = `data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`;
const { buildSequenceIssueDetails, buildSequenceIssueMarkIds, buildSequenceQualitySummary } = await import(moduleUrl);

test("sequence quality is ready for ordinary clip ranges", () => {
  assert.deepEqual(
    buildSequenceQualitySummary([
      { start_seconds: 0, end_seconds: 12 },
      { start_seconds: 20, end_seconds: 35 },
    ]),
    {
      issues: [],
      message: "序列检查正常",
      severity: "ready",
    },
  );
});

test("sequence quality warns on overlaps and short clips", () => {
  const summary = buildSequenceQualitySummary([
    { start_seconds: 0, end_seconds: 2 },
    { start_seconds: 1, end_seconds: 8 },
  ]);
  assert.equal(summary.severity, "warn");
  assert.deepEqual(summary.issues, [
    {
      id: "overlap",
      label: "重叠",
      markId: undefined,
      message: "1 处时间重叠",
      severity: "warn",
    },
    {
      id: "short",
      label: "短片段",
      markId: undefined,
      message: "1 段短于 3 秒",
      severity: "warn",
    },
  ]);
});

test("sequence quality blocks invalid clip boundaries", () => {
  const summary = buildSequenceQualitySummary([{ id: 42, start_seconds: 10, end_seconds: 4 }]);
  assert.equal(summary.severity, "block");
  assert.deepEqual(summary.issues[0], {
    id: "invalid-boundaries",
    label: "边界",
    markId: 42,
    message: "1 段出点不晚于入点",
    severity: "block",
  });
});

test("sequence quality points overlap and short issues to a clip", () => {
  const summary = buildSequenceQualitySummary([
    { id: 7, start_seconds: 0, end_seconds: 2 },
    { id: 8, start_seconds: 1, end_seconds: 8 },
  ]);
  assert.equal(summary.issues.find((issue) => issue.id === "overlap")?.markId, 8);
  assert.equal(summary.issues.find((issue) => issue.id === "short")?.markId, 7);
});

test("sequence issue mark ids include invalid, short, and overlapping clips", () => {
  const issueIds = buildSequenceIssueMarkIds([
    { id: 1, start_seconds: 0, end_seconds: 6 },
    { id: 2, start_seconds: 5, end_seconds: 9 },
    { id: 3, start_seconds: 12, end_seconds: 13 },
    { id: 4, start_seconds: 20, end_seconds: 18 },
    { id: 5, start_seconds: 30, end_seconds: 40 },
  ]);
  assert.deepEqual([...issueIds].sort((left, right) => left - right), [1, 2, 3, 4]);
});

test("sequence issue details describe the problem on each affected clip", () => {
  const details = buildSequenceIssueDetails([
    { id: 1, start_seconds: 0, end_seconds: 6 },
    { id: 2, start_seconds: 5, end_seconds: 9 },
    { id: 3, start_seconds: 12, end_seconds: 13 },
    { id: 4, start_seconds: 20, end_seconds: 18 },
  ]);
  assert.deepEqual(
    details.get(1).map((issue) => issue.message),
    ["与下一段重叠"],
  );
  assert.equal(details.get(1)[0].seekSeconds, 6);
  assert.deepEqual(
    details.get(2).map((issue) => issue.message),
    ["与上一段重叠"],
  );
  assert.equal(details.get(2)[0].seekSeconds, 5);
  assert.deepEqual(details.get(3), [{ id: "short", label: "短片段", message: "短于 3 秒", seekSeconds: 12, severity: "warn" }]);
  assert.deepEqual(details.get(4), [{ id: "invalid-boundaries", label: "边界", message: "出点不晚于入点", seekSeconds: 20, severity: "block" }]);
});
