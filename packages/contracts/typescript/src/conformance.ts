import { readFileSync } from "node:fs";
import { resolve } from "node:path";

type JsonRecord = Record<string, unknown>;

interface Manifest {
  fixtures: {
    auth: {
      verify_success: string;
      verify_401_invalid_token: string;
      verify_403_insufficient_scope: string;
    };
    transfer: {
      initiate_request: string;
      initiate_success: string;
    };
    jobs: {
      enqueue_request: string;
      enqueue_success: string;
      status_success: string;
      enqueue_503_queue_unavailable: string;
    };
  };
}

interface ErrorEnvelope {
  code: string;
  message: string;
  request_id: string;
}

function fixtureRoot(): string {
  return resolve(process.cwd(), "..", "fixtures", "v1");
}

function readJson<T>(relativePath: string): T {
  const raw = readFileSync(resolve(fixtureRoot(), relativePath), "utf-8");
  return JSON.parse(raw) as T;
}

function assert(cond: boolean, message: string): void {
  if (!cond) {
    throw new Error(message);
  }
}

function asRecord(value: unknown): JsonRecord {
  assert(typeof value === "object" && value !== null, "expected object payload");
  return value as JsonRecord;
}

function assertErrorEnvelope(value: unknown, code: string): void {
  const error = asRecord(value) as unknown as ErrorEnvelope;
  assert(error.code === code, `error.code must be ${code}`);
  assert(Boolean(error.message), "error.message required");
  assert(Boolean(error.request_id), "error.request_id required");
}

function main(): void {
  const manifest = readJson<Manifest>("manifest.json");

  const verifySuccess = asRecord(readJson<unknown>(manifest.fixtures.auth.verify_success));
  const verify401 = asRecord(readJson<unknown>(manifest.fixtures.auth.verify_401_invalid_token));
  const verify403 = asRecord(readJson<unknown>(manifest.fixtures.auth.verify_403_insufficient_scope));
  const transferRequest = asRecord(readJson<unknown>(manifest.fixtures.transfer.initiate_request));
  const queue503 = asRecord(
    readJson<unknown>(manifest.fixtures.jobs.enqueue_503_queue_unavailable),
  );

  const principal = asRecord(verifySuccess.principal);
  assert(typeof principal.subject === "string", "principal.subject required");
  assert(Array.isArray(principal.scopes), "principal.scopes required");

  assertErrorEnvelope(verify401.error, "invalid_token");
  assertErrorEnvelope(verify403.error, "insufficient_scope");
  assertErrorEnvelope(queue503.error, "queue_unavailable");

  assert(typeof transferRequest.session_id === "string", "session_id required");

  console.log("typescript conformance lane passed");
}

main();
