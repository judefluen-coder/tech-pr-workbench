import { existsSync, copyFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { spawn, spawnSync } from "node:child_process";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const args = new Set(process.argv.slice(2));
const installOnly = args.has("--install-only");
const skipInstall = args.has("--skip-install");

function command(name) {
  return process.platform === "win32" ? `${name}.cmd` : name;
}

function runChecked(label, cmd, cmdArgs) {
  console.log(`\n[${label}] ${cmd} ${cmdArgs.join(" ")}`);
  const result = spawnSync(cmd, cmdArgs, { cwd: root, stdio: "inherit" });
  if (result.status !== 0) {
    process.exit(result.status ?? 1);
  }
}

function ensureCommand(label, cmd) {
  const result = spawnSync(cmd, ["--version"], { cwd: root, stdio: "ignore" });
  if (result.status !== 0) {
    console.error(`Missing ${label}. Install it first, then rerun this command.`);
    process.exit(1);
  }
}

function ensureEnv() {
  const envPath = join(root, ".env");
  if (!existsSync(envPath)) {
    copyFileSync(join(root, ".env.example"), envPath);
    console.log("Created .env from .env.example. Add API keys there if you need them.");
  }
}

function install() {
  ensureCommand("uv", "uv");
  ensureCommand("npm", command("npm"));
  ensureEnv();
  runChecked("backend", "uv", ["sync", "--project", "backend", "--extra", "local-translation", "--extra", "test"]);
  runChecked("frontend", command("npm"), ["install", "--prefix", "frontend"]);
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
