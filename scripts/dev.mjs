import { existsSync, copyFileSync, readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { spawn, spawnSync } from "node:child_process";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const args = new Set(process.argv.slice(2));
const installOnly = args.has("--install-only");
const skipInstall = args.has("--skip-install");
const checkOnly = args.has("--check-only");

function command(name) {
  return process.platform === "win32" ? `${name}.cmd` : name;
}

function readEnvConfig() {
  const envPath = existsSync(join(root, ".env")) ? join(root, ".env") : join(root, ".env.example");
  const values = {};
  try {
    for (const line of readFileSync(envPath, "utf8").split(/\r?\n/)) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith("#")) continue;
      const match = trimmed.match(/^([A-Za-z_][A-Za-z0-9_]*)=(.*)$/);
      if (!match) continue;
      values[match[1]] = match[2].trim().replace(/^['"]|['"]$/g, "");
    }
  } catch {
    return values;
  }
  return values;
}

function configuredValue(env, key, fallback) {
  return process.env[key] || env[key] || fallback;
}

function runChecked(label, cmd, cmdArgs) {
  console.log(`\n[${label}] ${cmd} ${cmdArgs.join(" ")}`);
  const result = spawnSync(cmd, cmdArgs, { cwd: root, stdio: "inherit" });
  if (result.status !== 0) {
    process.exit(result.status ?? 1);
  }
}

function commandCheck(cmd, versionArgs = ["--version"]) {
  const result = spawnSync(cmd, versionArgs, { cwd: root, encoding: "utf8" });
  return {
    ok: result.status === 0,
    output: `${result.stdout || ""}${result.stderr || ""}`.trim().split("\n")[0] || "",
  };
}

function requireCommand(label, cmd, installHint, versionArgs = ["--version"]) {
  const result = commandCheck(cmd, versionArgs);
  if (!result.ok) {
    console.error(`Missing ${label}. ${installHint}`);
    process.exit(1);
  }
  return result;
}

function ensureEnv() {
  const envPath = join(root, ".env");
  if (!existsSync(envPath)) {
    copyFileSync(join(root, ".env.example"), envPath);
    console.log("Created .env from .env.example. Add API keys there if you need them.");
  }
}

function install() {
  doctor({ strict: true });
  ensureEnv();
  runChecked("backend", "uv", ["sync", "--project", "backend", "--extra", "local-translation", "--extra", "test"]);
  runChecked("frontend", command("npm"), ["install", "--prefix", "frontend"]);
}

function doctor({ strict = false } = {}) {
  const env = readEnvConfig();
  const opencliCommand = configuredValue(env, "OPENCLI_PATH", "opencli");
  const required = [
    ["Node.js", command("node"), "Install Node.js 20+ first. macOS: brew install node", ["--version"]],
    ["npm", command("npm"), "Install npm with Node.js first.", ["--version"]],
    ["uv", "uv", "Install uv first. macOS: brew install uv", ["--version"]],
    ["FFmpeg", "ffmpeg", "Install FFmpeg first. macOS: brew install ffmpeg", ["-version"]],
  ];
  console.log("\nDependency check");
  console.log("----------------");
  for (const [label, cmd, hint, versionArgs] of required) {
    const result = strict ? requireCommand(label, cmd, hint, versionArgs) : commandCheck(cmd, versionArgs);
    console.log(`${result.ok ? "OK " : "NO "} ${label}${result.output ? ` - ${result.output}` : ""}`);
    if (!result.ok) {
      console.log(`    ${hint}`);
    }
  }

  const optional = [
    [`opencli (${opencliCommand})`, opencliCommand, "Optional fallback for YouTube search when no YouTube API key is configured."],
    ["Ollama", "ollama", "Optional local LLM translation fallback."],
  ];
  console.log("\nOptional tools");
  console.log("--------------");
  for (const [label, cmd, note] of optional) {
    const result = commandCheck(cmd);
    console.log(`${result.ok ? "OK " : "-- "} ${label}${result.output ? ` - ${result.output}` : ""}`);
    if (!result.ok) {
      console.log(`    ${note}`);
    }
  }

  console.log("\nInstalled by npm run setup");
  console.log("--------------------------");
  console.log("- Backend Python packages, including yt-dlp and Argos Translate.");
  console.log("- Frontend npm packages.");
  console.log("- .env copied from .env.example when missing.");
  console.log("\nNot installed automatically");
  console.log("---------------------------");
  console.log("- YouTube API key, because users must create their own key.");
  console.log("- OpenAI SDK, unless users explicitly install backend[cloud-ai].");
  console.log("- faster-whisper, unless users explicitly install backend[local-asr].");
  console.log("- XiaDown, because it is an external companion downloader, not a built-in engine.");
  console.log("- Argos language model may download on first translation when ARGOS_AUTO_INSTALL=true.");
}

function startProcess(label, cmd, cmdArgs) {
  const child = spawn(cmd, cmdArgs, { cwd: root, stdio: "inherit" });
  child.on("exit", (code) => {
    if (code && !shuttingDown) {
      console.error(`[${label}] exited with code ${code}`);
      shutdown(code);
    }
  });
  return child;
}

let shuttingDown = false;
let children = [];

function shutdown(code = 0) {
  if (shuttingDown) return;
  shuttingDown = true;
  for (const child of children) {
    child.kill("SIGTERM");
  }
  setTimeout(() => process.exit(code), 300).unref();
}

if (checkOnly) {
  doctor();
  process.exit(0);
}

if (!skipInstall) {
  install();
}

if (installOnly) {
  console.log("\nSetup complete. Run `npm run dev` to start the workbench.");
  process.exit(0);
}

console.log("\nStarting Tech PR Workbench:");
console.log("- Backend:  http://127.0.0.1:8000");
console.log("- Frontend: http://127.0.0.1:5173");
console.log("Press Ctrl+C to stop both processes.\n");

children = [
  startProcess("backend", "uv", ["run", "--project", "backend", "uvicorn", "--app-dir", "backend", "app.main:app", "--reload", "--host", "127.0.0.1", "--port", "8000"]),
  startProcess("frontend", command("npm"), ["run", "dev", "--prefix", "frontend"]),
];

process.on("SIGINT", () => shutdown(0));
process.on("SIGTERM", () => shutdown(0));
