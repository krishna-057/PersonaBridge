import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

const requiredFiles = [
  "package.json",
  ".env.example",
  "CONTRACTS.md",
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
if (
  !appPage.includes("/api/sessions") ||
  !appPage.includes("/approvals") ||
  !appPage.includes("/realtime-contract") ||
  !appPage.includes("/memory-contract")
) {
  throw new Error("Web app must exercise session, approval, realtime, and memory contract boundaries.");
}

const apiFile = readFileSync("services/api/app/main.py", "utf8");
if (
  !apiFile.includes("approval_gate") ||
  !apiFile.includes("/api/sessions/{session_id}/messages") ||
  !apiFile.includes("/api/sessions/{session_id}/realtime-contract") ||
  !apiFile.includes("/api/sessions/{session_id}/memory-contract")
) {
  throw new Error("API must expose chat messages, approval-gated tool requests, and contract endpoints.");
}

const contractsDoc = readFileSync("CONTRACTS.md", "utf8");
if (!contractsDoc.includes("Realtime Session Contract") || !contractsDoc.includes("Memory Contract")) {
  throw new Error("CONTRACTS.md must define realtime and memory contracts.");
}

console.log("PersonaBridge scaffold check passed.");
