import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

const requiredFiles = [
  "package.json",
  ".env.example",
  "apps/web/package.json",
  "apps/web/src/app/page.tsx",
  "apps/web/src/app/layout.tsx",
  "services/api/Dockerfile",
  "services/api/requirements.txt",
  "services/api/app/main.py"
];

const rootPackage = JSON.parse(readFileSync("package.json", "utf8"));
if (!Array.isArray(rootPackage.workspaces) || !rootPackage.workspaces.includes("apps/*")) {
  throw new Error("Root package.json must declare apps/* workspaces.");
}

for (const file of requiredFiles) {
  if (!existsSync(join(process.cwd(), file))) {
    throw new Error(`Missing scaffold file: ${file}`);
  }
}

const appPage = readFileSync("apps/web/src/app/page.tsx", "utf8");
if (!appPage.includes("/api/sessions") || !appPage.includes("/approvals")) {
  throw new Error("Web app must exercise session and approval API boundaries.");
}

const apiFile = readFileSync("services/api/app/main.py", "utf8");
if (!apiFile.includes("approval_gate") || !apiFile.includes("/api/sessions/{session_id}/messages")) {
  throw new Error("API must expose chat messages and approval-gated tool requests.");
}

console.log("PersonaBridge scaffold check passed.");
