import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { createNovaFileClient } from "@nova/sdk-file/client";
import {
  NovaSdkHttpError as NovaFileSdkHttpError,
  assertOkResponse as assertFileOkResponse,
} from "@nova/sdk-file/errors";
import { operations as fileOperations } from "@nova/sdk-file/operations";
import type {
  CreateJobRequestBody,
  InitiateUploadRequestBody,
} from "@nova/sdk-file/types";
import { buildOperationDescriptorUrl, buildOperationUrl } from "@nova/sdk-fetch/url";

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
  readonly assertRequest?: (request: {
    readonly url: string;
    readonly init: RequestInit | undefined;
  }) => void;
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

function bodyToString(body: RequestInit["body"] | null | undefined): string {
  if (typeof body === "string") {
    return body;
  }
  if (body instanceof URLSearchParams) {
    return body.toString();
  }
  throw new Error("expected string or URLSearchParams request body");
}

function createFixtureFetch(
  routes: Record<string, MockResponseFixture>,
): typeof fetch {
  return async (input, init) => {
    const url =
      typeof input === "string"
        ? input
        : input instanceof URL
          ? input.toString()
          : input.url;
    const fixture = routes[url];
    assert(Boolean(fixture), `unexpected request URL: ${url}`);
    fixture.assertRequest?.({ url, init });
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
  const planFixture = readJson<unknown>(manifest.fixtures.v1api.resources_plan_success);
  const expectedPlanPayload = {
    resources: ["jobs", "transfers"],
  };
  const releaseFixture = readJson<unknown>(
    manifest.fixtures.v1api.releases_info_success,
  );

  const fileBaseUrl = "https://file.nova.example/";
  const getJobUrl = buildOperationDescriptorUrl(
    fileBaseUrl,
    fileOperations.get_job_status,
    { job_id: "job-123" },
  );
  const createJobUrl = buildOperationDescriptorUrl(
    fileBaseUrl,
    fileOperations.create_job,
  );
  const initiateUploadUrl = buildOperationDescriptorUrl(
    fileBaseUrl,
    fileOperations.initiate_upload,
  );
  const capabilitiesUrl = buildOperationDescriptorUrl(
    fileBaseUrl,
    fileOperations.get_capabilities,
  );
  const planUrl = buildOperationDescriptorUrl(
    fileBaseUrl,
    fileOperations.plan_resources,
  );
  const releaseUrl = buildOperationDescriptorUrl(
    fileBaseUrl,
    fileOperations.get_release_info,
  );

  const fileUrl = buildOperationUrl(
    "https://nova.example/",
    fileOperations.get_job_status.path,
    { job_id: "job-123" },
    { include: "events" },
  );
  assert(
    fileUrl === "https://nova.example/v1/jobs/job-123?include=events",
    `unexpected file URL: ${fileUrl}`,
  );

  const descriptorUrl = buildOperationDescriptorUrl(
    "https://nova.example/",
    fileOperations.get_job_status,
    { job_id: "job-123" },
    { include: "events" },
  );
  assert(
    descriptorUrl === "https://nova.example/v1/jobs/job-123?include=events",
    `unexpected descriptor URL: ${descriptorUrl}`,
  );

  const fileClient = createNovaFileClient({
    baseUrl: fileBaseUrl,
    fetchImpl: createFixtureFetch({
      [getJobUrl]: {
        status: 200,
        body: jobStatusFixture,
        assertRequest: ({ init }) => {
          assert(init?.method === "GET", "get_job_status must use GET");
        },
      },
      [createJobUrl]: {
        status: 202,
        body: enqueueSuccessFixture,
        assertRequest: ({ init }) => {
          assert(init?.method === "POST", "create_job must use POST");
          const headers = new Headers(init?.headers);
          assert(
            headers.get("content-type")?.startsWith("application/json") ?? false,
            "create_job must use application/json content type",
          );
          assert(
            bodyToString(init?.body) === JSON.stringify(enqueueRequestFixture),
            "create_job must send JSON request body",
          );
        },
      },
      [initiateUploadUrl]: {
        status: 200,
        body: transferSuccessFixture,
        assertRequest: ({ init }) => {
          assert(init?.method === "POST", "initiate_upload must use POST");
          const headers = new Headers(init?.headers);
          assert(
            headers.get("content-type")?.startsWith("application/json") ?? false,
            "initiate_upload must use application/json content type",
          );
          assert(
            bodyToString(init?.body) === JSON.stringify(transferRequestFixture),
            "initiate_upload must send JSON request body",
          );
        },
      },
      [capabilitiesUrl]: {
        status: 200,
        body: capabilitiesFixture,
        assertRequest: ({ init }) => {
          assert(init?.method === "GET", "get_capabilities must use GET");
        },
      },
      [planUrl]: {
        status: 200,
        body: planFixture,
        assertRequest: ({ init }) => {
          assert(init?.method === "POST", "plan_resources must use POST");
          const headers = new Headers(init?.headers);
          assert(
            headers.get("content-type")?.toLowerCase().includes("application/json") ??
              false,
            "plan_resources must use application/json content type",
          );
          assert(
            JSON.stringify(JSON.parse(bodyToString(init?.body))) ===
              JSON.stringify(expectedPlanPayload),
            "plan_resources must send JSON request body",
          );
        },
      },
      [releaseUrl]: {
        status: 200,
        body: releaseFixture,
        assertRequest: ({ init }) => {
          assert(init?.method === "GET", "get_release_info must use GET");
        },
      },
    }),
  });
  assert(
    fileClient.baseUrl === "https://file.nova.example",
    "file client baseUrl must be normalized",
  );

  const jobStatusResult = await fileClient.get_job_status({
    pathParams: { job_id: "job-123" },
  });
  assert(jobStatusResult.ok, "get_job_status fixture must be ok");
  assertFileOkResponse("get_job_status", jobStatusResult);
  assert(
    typeof asRecord(jobStatusResult.data?.job).job_id === "string",
    "job result must include job_id",
  );

  const createJobResult = await fileClient.create_job({
    body: enqueueRequestFixture,
  });
  assert(createJobResult.ok, "create_job success fixture must be ok");
  assertFileOkResponse("create_job", createJobResult);

  const initiateResult = await fileClient.initiate_upload({
    body: transferRequestFixture,
  });
  assert(initiateResult.ok, "initiate_upload fixture must be ok");
  assertFileOkResponse("initiate_upload", initiateResult);

  const capabilitiesResult = await fileClient.get_capabilities();
  assert(capabilitiesResult.ok, "get_capabilities fixture must be ok");
  assertFileOkResponse("get_capabilities", capabilitiesResult);

  const planResult = await fileClient.plan_resources({
    body: expectedPlanPayload,
  });
  assert(planResult.ok, "plan_resources fixture must be ok");
  assertFileOkResponse("plan_resources", planResult);

  const releaseResult = await fileClient.get_release_info();
  assert(releaseResult.ok, "get_release_info fixture must be ok");
  assertFileOkResponse("get_release_info", releaseResult);

  const queueUnavailableClient = createNovaFileClient({
    baseUrl: fileBaseUrl,
    fetchImpl: createFixtureFetch({
      [createJobUrl]: {
        status: 503,
        body: queueUnavailableFixture,
      },
    }),
  });
  const queueUnavailableResult = await queueUnavailableClient.create_job({
    body: enqueueRequestFixture,
  });
  assert(
    !queueUnavailableResult.ok,
    "create_job queue unavailable fixture must not be ok",
  );
  assertErrorEnvelope(
    asRecord(queueUnavailableResult.data).error,
    "queue_unavailable",
  );

  let sawFileHttpError = false;
  try {
    assertFileOkResponse("create_job", queueUnavailableResult);
  } catch (error) {
    sawFileHttpError = error instanceof NovaFileSdkHttpError;
  }
  assert(sawFileHttpError, "assertFileOkResponse must throw NovaSdkHttpError");

  assert(
    !("update_job_result" in fileOperations),
    "internal file operation leaked into public SDK",
  );
}

main().catch((error: unknown) => {
  console.error(error);
  process.exitCode = 1;
});
