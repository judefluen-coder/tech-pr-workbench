import assert from "node:assert/strict";
import { chmodSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { spawnSync } from "node:child_process";
import test from "node:test";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");

test("doctor reports Node 20.18 as unsupported", () => {
  const fakeBin = mkdtempSync(join(tmpdir(), "tech-pr-doctor-"));
  const fakeNode = join(fakeBin, "node");
  writeFileSync(fakeNode, "#!/bin/sh\nif [ \"$1\" = \"--version\" ]; then echo v20.18.0; exit 0; fi\nexit 1\n");
  chmodSync(fakeNode, 0o755);

  try {
    const result = spawnSync(process.execPath, ["scripts/dev.mjs", "--check-only"], {
      cwd: root,
      env: { ...process.env, PATH: `${fakeBin}:${process.env.PATH}` },
      encoding: "utf8",
    });
    const output = `${result.stdout}\n${result.stderr}`;
    assert.equal(result.status, 0);
    assert.match(output, /NO\s+Node\.js - v20\.18\.0/);
    assert.match(output, /Install Node\.js >=20\.19\.0 or >=22\.12\.0/);
  } finally {
    rmSync(fakeBin, { recursive: true, force: true });
  }
});
