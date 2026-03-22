import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import {
  createNovaFileClient,
  type NovaFileClientMiddleware,
} from "@nova/sdk-file/client";
import {
  NovaSdkHttpError as NovaFileSdkHttpError,
  assertOkResponse as assertFileOkResponse,
} from "@nova/sdk-file/errors";
import { operations as fileOperations } from "@nova/sdk-file/operations";
import type {
  CreateJobRequestBody,
  InitiateUploadRequestBody,
} from "@nova/sdk-file/types";

type JsonRecord = Record<string, unknown>;

interface Manifest {
  fixtures: {
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
    v1api: {
      capabilities_success: string;
      resources_plan_success: string;
      releases_info_success: string;
    };
  };
}

interface ErrorEnvelope {
  code: string;
  message: string;
  request_id: string;
}

type AssertFalse<T extends false> = T;
type FileTypeModule = typeof import("@nova/sdk-file/types");

type _NoFileComponentsExport = AssertFalse<
  "Components" extends keyof FileTypeModule ? true : false
>;
type _NoFilePathsExport = AssertFalse<
  "Paths" extends keyof FileTypeModule ? true : false
>;
type _NoFileOperationsExport = AssertFalse<
  "Operations" extends keyof FileTypeModule ? true : false
>;
type _NoFileOperationIdExport = AssertFalse<
  "OperationId" extends keyof FileTypeModule ? true : false
>;
type _NoInternalJobResultUpdateRequestExport = AssertFalse<
  "JobResultUpdateRequest" extends keyof FileTypeModule ? true : false
>;
type _NoInternalJobResultUpdateResponseExport = AssertFalse<
  "JobResultUpdateResponse" extends keyof FileTypeModule ? true : false
>;

interface MockResponseFixture {
  readonly status: number;
  readonly body: unknown;
  readonly assertRequest?: (request: Request) => Promise<void> | void;
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

async function requestBodyText(request: Request): Promise<string> {
  return request.text();
}

function createFixtureFetch(
  routes: Record<string, MockResponseFixture>,
): (input: Request) => Promise<Response> {
  return async (input) => {
    const fixture = routes[input.url];
    assert(Boolean(fixture), `unexpected request URL: ${input.url}`);
    await fixture.assertRequest?.(input);
    return new Response(JSON.stringify(fixture.body), {
      status: fixture.status,
      headers: { "content-type": "application/json" },
    });
  };
}

async function main(): Promise<void> {
  const manifest = readJson<Manifest>("manifest.json");

  const transferRequestFixture = readJson<InitiateUploadRequestBody>(
    manifest.fixtures.transfer.initiate_request,
  );
  const transferSuccessFixture = readJson<unknown>(
    manifest.fixtures.transfer.initiate_success,
  );
  const enqueueRequestFixture = readJson<CreateJobRequestBody>(
    manifest.fixtures.jobs.enqueue_request,
  );
  const enqueueSuccessFixture = readJson<unknown>(
    manifest.fixtures.jobs.enqueue_success,
  );
  const queueUnavailableFixture = readJson<unknown>(
    manifest.fixtures.jobs.enqueue_503_queue_unavailable,
  );
  const jobStatusFixture = readJson<unknown>(
    manifest.fixtures.jobs.status_success,
  );
  const capabilitiesFixture = readJson<unknown>(
    manifest.fixtures.v1api.capabilities_success,
  );
  const planFixture = readJson<unknown>(
    manifest.fixtures.v1api.resources_plan_success,
  );
  const expectedPlanPayload = {
    resources: ["jobs", "transfers"],
  };
  const releaseFixture = readJson<unknown>(
    manifest.fixtures.v1api.releases_info_success,
  );

  const fileBaseUrl = "https://file.nova.example/";
  const getJobUrl = "https://file.nova.example/v1/jobs/job-123";
  const createJobUrl = "https://file.nova.example/v1/jobs";
  const initiateUploadUrl =
    "https://file.nova.example/v1/transfers/uploads/initiate";
  const capabilitiesUrl = "https://file.nova.example/v1/capabilities";
  const planUrl = "https://file.nova.example/v1/resources/plan";
  const releaseUrl = "https://file.nova.example/v1/releases/info";

  assert(
    fileOperations.get_job_status.path === "/v1/jobs/{job_id}",
    "get_job_status path must remain canonical",
  );
  assert(
    fileOperations.create_job.method === "POST",
    "create_job method must remain canonical",
  );

  const middleware: NovaFileClientMiddleware = {
    onRequest({ request }) {
      const headers = new Headers(request.headers);
      headers.set("authorization", "Bearer test-token");
      headers.set("x-request-id", "req-123");
      return new Request(request, { headers });
    },
  };

  const fileClient = createNovaFileClient({
    baseUrl: fileBaseUrl,
    fetch: createFixtureFetch({
      [getJobUrl]: {
        status: 200,
        body: jobStatusFixture,
        assertRequest: (request) => {
          assert(request.method === "GET", "get_job_status must use GET");
          assert(
            request.headers.get("authorization") === "Bearer test-token",
            "middleware must inject authorization header",
          );
          assert(
            request.headers.get("x-request-id") === "req-123",
            "middleware must inject request id header",
          );
        },
      },
      [createJobUrl]: {
        status: 202,
        body: enqueueSuccessFixture,
        assertRequest: async (request) => {
          assert(request.method === "POST", "create_job must use POST");
          assert(
            request.headers.get("content-type")?.startsWith("application/json") ??
              false,
            "create_job must use application/json content type",
          );
          assert(
            (await requestBodyText(request)) === JSON.stringify(enqueueRequestFixture),
            "create_job must send JSON request body",
          );
        },
      },
      [initiateUploadUrl]: {
        status: 200,
        body: transferSuccessFixture,
        assertRequest: async (request) => {
          assert(request.method === "POST", "initiate_upload must use POST");
          assert(
            request.headers.get("content-type")?.startsWith("application/json") ??
              false,
            "initiate_upload must use application/json content type",
          );
          assert(
            (await requestBodyText(request)) === JSON.stringify(transferRequestFixture),
            "initiate_upload must send JSON request body",
          );
        },
      },
      [capabilitiesUrl]: {
        status: 200,
        body: capabilitiesFixture,
        assertRequest: (request) => {
          assert(request.method === "GET", "get_capabilities must use GET");
        },
      },
      [planUrl]: {
        status: 200,
        body: planFixture,
        assertRequest: async (request) => {
          assert(request.method === "POST", "plan_resources must use POST");
          assert(
            request.headers.get("content-type")?.toLowerCase().includes("application/json") ??
              false,
            "plan_resources must use application/json content type",
          );
          assert(
            JSON.stringify(JSON.parse(await requestBodyText(request))) ===
              JSON.stringify(expectedPlanPayload),
            "plan_resources must send JSON request body",
          );
        },
      },
      [releaseUrl]: {
        status: 200,
        body: releaseFixture,
        assertRequest: (request) => {
          assert(request.method === "GET", "get_release_info must use GET");
        },
      },
    }),
    middleware: [middleware],
  });

  const jobStatusResult = await fileClient.GET(fileOperations.get_job_status.path, {
    params: { path: { job_id: "job-123" } },
  });
  assertFileOkResponse("get_job_status", jobStatusResult);
  assert(
    typeof asRecord(jobStatusResult.data.job).job_id === "string",
    "job result must include job_id",
  );

  const createJobResult = await fileClient.POST(fileOperations.create_job.path, {
    body: enqueueRequestFixture,
  });
  assertFileOkResponse("create_job", createJobResult);

  const initiateResult = await fileClient.POST(fileOperations.initiate_upload.path, {
    body: transferRequestFixture,
  });
  assertFileOkResponse("initiate_upload", initiateResult);

  const capabilitiesResult = await fileClient.GET(
    fileOperations.get_capabilities.path,
  );
  assertFileOkResponse("get_capabilities", capabilitiesResult);

  const planResult = await fileClient.POST(fileOperations.plan_resources.path, {
    body: expectedPlanPayload,
  });
  assertFileOkResponse("plan_resources", planResult);

  const releaseResult = await fileClient.GET(fileOperations.get_release_info.path);
  assertFileOkResponse("get_release_info", releaseResult);

  const queueUnavailableClient = createNovaFileClient({
    baseUrl: fileBaseUrl,
    fetch: createFixtureFetch({
      [createJobUrl]: {
        status: 503,
        body: queueUnavailableFixture,
      },
    }),
  });
  const queueUnavailableResult = await queueUnavailableClient.POST(
    fileOperations.create_job.path,
    {
      body: enqueueRequestFixture,
    },
  );
  assert(
    queueUnavailableResult.error !== undefined,
    "create_job queue unavailable fixture must return the error arm",
  );
  assertErrorEnvelope(
    asRecord(queueUnavailableResult.error).error,
    "queue_unavailable",
  );

  let sawFileHttpError = false;
  try {
    assertFileOkResponse("create_job", queueUnavailableResult);
  } catch (error) {
    sawFileHttpError =
      error instanceof NovaFileSdkHttpError && error.status === 503;
  }
  assert(sawFileHttpError, "assertFileOkResponse must throw NovaSdkHttpError");

  assert(
    !("update_job_result" in fileOperations),
    "internal worker operation must stay excluded from public operations",
  );
}

void main().catch((error: unknown) => {
  console.error(error);
  process.exitCode = 1;
});
