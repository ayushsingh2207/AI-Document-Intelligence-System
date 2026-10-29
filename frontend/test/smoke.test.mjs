import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const frontendRoot = path.resolve(__dirname, "..");

test("Frontend architectural smoke test: required files exist", () => {
  const requiredFiles = [
    "src/app/page.tsx",
    "src/app/layout.tsx",
    "src/app/globals.css",
    "src/components/Navbar.tsx",
    "src/components/MetricsCards.tsx",
    "src/components/FileUpload.tsx",
    "src/components/DocumentViewer.tsx",
    "src/components/SearchInterface.tsx",
    "src/components/ContractInterface.tsx",
    "src/lib/api.ts",
    ".env.example",
    "package.json",
    "tsconfig.json",
  ];

  for (const relPath of requiredFiles) {
    const fullPath = path.join(frontendRoot, relPath);
    assert.equal(
      fs.existsSync(fullPath),
      true,
      `Expected ${relPath} to exist in frontend`
    );
  }
});

test("Frontend API client exports required interfaces and methods", () => {
  const apiPath = path.join(frontendRoot, "src/lib/api.ts");
  const content = fs.readFileSync(apiPath, "utf-8");

  assert.match(content, /export interface DocumentPage/);
  assert.match(content, /export interface DocumentExtractionResponse/);
  assert.match(content, /export interface HealthResponse/);
  assert.match(content, /export async function checkBackendHealth/);
  assert.match(content, /export async function uploadDocument/);
  assert.match(content, /is_approximate/);
  assert.match(content, /boundary_type/);
  assert.match(content, /RetrievalStrategy/);
  assert.match(content, /getBM25Stats/);
  assert.match(content, /BM25StatsResponse/);
  assert.match(content, /export interface Citation/);
  assert.match(content, /export interface QARequest/);
  assert.match(content, /export interface QAResponse/);
  assert.match(content, /export async function askQuestion/);
  assert.match(content, /export interface ClauseSpan/);
  assert.match(content, /export interface ContractAnalysisRequest/);
  assert.match(content, /export interface ContractAnalysisResponse/);
  assert.match(content, /export async function analyzeContract/);
  assert.match(content, /export async function getContractCategories/);
});

test("Frontend environment example contains NEXT_PUBLIC_API_URL", () => {
  const envPath = path.join(frontendRoot, ".env.example");
  const content = fs.readFileSync(envPath, "utf-8");
  assert.match(content, /NEXT_PUBLIC_API_URL=/);
});
