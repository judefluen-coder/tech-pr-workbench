import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import ts from "../frontend/node_modules/typescript/lib/typescript.js";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const source = readFileSync(resolve(root, "frontend/src/lib/clipSequenceFocus.ts"), "utf8");
const { outputText } = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.ES2022,
    target: ts.ScriptTarget.ES2022,
  },
});
const moduleUrl = `data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`;
const { clipSequenceFocusSelectors } = await import(moduleUrl);

test("sequence focus selectors prioritize missing copy flags", () => {
  assert.deepEqual(clipSequenceFocusSelectors("copy"), [".marks-panel .mark-quality-flags .copy", ".marks-panel"]);
});

test("sequence focus selectors prioritize blocking and warning issue flags", () => {
  assert.deepEqual(clipSequenceFocusSelectors("issues"), [".marks-panel .mark-quality-flags .block", ".marks-panel .mark-quality-flags .warn", ".marks-panel"]);
});

test("sequence focus selectors fall back to the sequence panel", () => {
  assert.deepEqual(clipSequenceFocusSelectors("approved"), [".marks-panel"]);
});
