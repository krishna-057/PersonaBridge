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
  !appPage.includes("/memory-contract") ||
  !appPage.includes("/memory-candidates") ||
  !appPage.includes("deleteMemoryCandidate") ||
  !appPage.includes("getUserMedia") ||
  !appPage.includes("Join Voice")
) {
  throw new Error("Web app must exercise session, approval, realtime, voice shell, and memory candidate boundaries.");
}

const apiFile = readFileSync("services/api/app/main.py", "utf8");
if (
  !apiFile.includes("approval_gate") ||
  !apiFile.includes("/api/sessions/{session_id}/messages") ||
  !apiFile.includes("/api/sessions/{session_id}/realtime-contract") ||
  !apiFile.includes("/api/sessions/{session_id}/memory-contract") ||
  !apiFile.includes("/api/sessions/{session_id}/realtime-token") ||
  !apiFile.includes("/api/sessions/{session_id}/memory-candidates") ||
  !apiFile.includes("/api/memory-candidates/{candidate_id}") ||
  !apiFile.includes("opaque_browser_join")
) {
  throw new Error("API must expose chat messages, approval-gated tool requests, contracts, realtime token minting, and memory candidate controls.");
}

const contractsDoc = readFileSync("CONTRACTS.md", "utf8");
if (
  !contractsDoc.includes("Realtime Session Contract") ||
  !contractsDoc.includes("Memory Contract") ||
  !contractsDoc.includes("Room Token Slice") ||
  !contractsDoc.includes("Memory Candidate Slice")
) {
  throw new Error("CONTRACTS.md must define realtime, room token, memory, and candidate contracts.");
}

console.log("PersonaBridge scaffold check passed.");
