const { spawnSync } = require("node:child_process");
const path = require("node:path");

const result = spawnSync(process.platform === "win32" ? "pnpm.cmd" : "pnpm", ["build"], {
  cwd: path.join(__dirname, "..", "apps", "web"),
  stdio: "inherit",
  shell: process.platform === "win32",
  env: { ...process.env, NEXT_PUBLIC_API_URL: "" },
});
if (result.error) console.error(result.error.message);
process.exit(result.status ?? 1);
