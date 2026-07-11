import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import ts from "../frontend/node_modules/typescript/lib/typescript.js";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const source = readFileSync(resolve(root, "frontend/src/lib/clipPreflight.ts"), "utf8");
const { outputText } = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.ES2022,
    target: ts.ScriptTarget.ES2022,
  },
});
const moduleUrl = `data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`;
const { buildExportVersionPlan, buildExportVersionPreflightCheck } = await import(moduleUrl);

test("export version plan follows sequence order and trims the last included clip", () => {
  assert.deepEqual(
    buildExportVersionPlan(
      [
        { start_seconds: 10, end_seconds: 30 },
        { start_seconds: 60, end_seconds: 95 },
        { start_seconds: 120, end_seconds: 140 },
      ],
      30,
    ),
    {
      duration: 30,
      includedCount: 2,
      shortfall: false,
      trimsLastClip: true,
    },
  );
});

test("export version plan reports shortfall when the sequence is shorter than the target", () => {
  assert.deepEqual(
    buildExportVersionPlan(
      [
        { start_seconds: 0, end_seconds: 8 },
        { start_seconds: 12, end_seconds: 20 },
      ],
      30,
    ),
    {
      duration: 16,
      includedCount: 2,
      shortfall: true,
      trimsLastClip: false,
    },
  );
});

test("export version preflight explains exactly how a target version will be cut", () => {
  assert.deepEqual(
    buildExportVersionPreflightCheck({
      marks: [
        { start_seconds: 0, end_seconds: 20 },
        { start_seconds: 30, end_seconds: 50 },
      ],
      sequenceDuration: 40,
      targetDuration: 30,
    }),
    {
      id: "version",
      label: "导出版本",
      message: "会导出 0:30 版本，使用前 2 段，并截短最后一段。",
      severity: "ready",
    },
  );
});

test("export version preflight warns when a target version cannot be filled", () => {
  assert.deepEqual(
    buildExportVersionPreflightCheck({
      marks: [{ start_seconds: 0, end_seconds: 12 }],
      sequenceDuration: 12,
      targetDuration: 30,
    }),
    {
      id: "version",
      label: "导出版本",
      message: "序列短于 0:30，会导出全部 0:12。",
      severity: "warn",
    },
  );
});

test("export version preflight keeps the full sequence message without a target", () => {
  assert.deepEqual(
    buildExportVersionPreflightCheck({
      marks: [{ start_seconds: 0, end_seconds: 12 }],
      sequenceDuration: 12,
      targetDuration: 0,
    }),
    {
      id: "version",
      label: "导出版本",
      message: "会导出完整序列。",
      severity: "ready",
    },
  );
});
