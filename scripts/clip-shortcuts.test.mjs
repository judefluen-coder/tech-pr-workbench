import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import ts from "../frontend/node_modules/typescript/lib/typescript.js";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const source = readFileSync(resolve(root, "frontend/src/lib/clipShortcuts.ts"), "utf8");
const { outputText } = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.ES2022,
    target: ts.ScriptTarget.ES2022,
  },
});
const moduleUrl = `data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`;
const { resolveClipEditShortcut } = await import(moduleUrl);

test("clip edit shortcuts resolve save and approve command keys", () => {
  assert.equal(resolveClipEditShortcut({ ctrlKey: true, key: "Enter" }), "save");
  assert.equal(resolveClipEditShortcut({ key: "Enter", metaKey: true, shiftKey: true }), "approve");
  assert.equal(resolveClipEditShortcut({ altKey: true, ctrlKey: true, key: "Enter" }), null);
});

test("clip edit shortcuts keep command keys active in text fields", () => {
  assert.equal(resolveClipEditShortcut({ ctrlKey: true, ignorePlainKeys: true, key: "Enter" }), "save");
  assert.equal(resolveClipEditShortcut({ ignorePlainKeys: true, key: "Escape" }), "cancel");
  assert.equal(resolveClipEditShortcut({ altKey: true, ignorePlainKeys: true, key: "ArrowDown" }), "next");
});

test("clip edit shortcuts ignore plain letter shortcuts while typing", () => {
  assert.equal(resolveClipEditShortcut({ ignorePlainKeys: true, key: "i" }), null);
  assert.equal(resolveClipEditShortcut({ ignorePlainKeys: true, key: "o" }), null);
  assert.equal(resolveClipEditShortcut({ ignorePlainKeys: true, key: "p" }), null);
  assert.equal(resolveClipEditShortcut({ ignorePlainKeys: true, key: " " }), null);
});

test("clip edit shortcuts resolve timeline actions outside typing targets", () => {
  assert.equal(resolveClipEditShortcut({ key: "i" }), "mark-in");
  assert.equal(resolveClipEditShortcut({ key: "O" }), "mark-out");
  assert.equal(resolveClipEditShortcut({ key: "p" }), "preview");
  assert.equal(resolveClipEditShortcut({ key: " " }), "preview");
  assert.equal(resolveClipEditShortcut({ altKey: true, key: "ArrowUp" }), "previous");
});
