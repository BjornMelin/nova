import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { createNovaAuthClient } from "@nova/sdk-auth/client";
import {
  NovaSdkHttpError as NovaAuthSdkHttpError,
  assertOkResponse as assertAuthOkResponse,
} from "@nova/sdk-auth/errors";
import { operations as authOperations } from "@nova/sdk-auth/operations";
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
import { buildOperationDescriptorUrl } from "@nova/sdk-fetch/url";

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
type AuthTypeModule = typeof import("@nova/sdk-auth/types");

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
type _NoAuthComponentsExport = AssertFalse<
  "Components" extends keyof AuthTypeModule ? true : false
>;
type _NoAuthPathsExport = AssertFalse<
  "Paths" extends keyof AuthTypeModule ? true : false
>;
type _NoAuthOperationsExport = AssertFalse<
  "Operations" extends keyof AuthTypeModule ? true : false
>;
type _NoAuthOperationIdExport = AssertFalse<
  "OperationId" extends keyof AuthTypeModule ? true : false
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

  const verifySuccessFixture = readJson<unknown>(manifest.fixtures.auth.verify_success);
  const verify401Fixture = readJson<unknown>(
    manifest.fixtures.auth.verify_401_invalid_token,
  );
  const verify403Fixture = readJson<unknown>(
    manifest.fixtures.auth.verify_403_insufficient_scope,
  );
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
  const releaseFixture = readJson<unknown>(
    manifest.fixtures.v1api.releases_info_success,
  );

  const authBaseUrl = "https://auth.nova.example/";
  const verifyUrl = buildOperationDescriptorUrl(
    authBaseUrl,
    authOperations.verify_token,
  );
  const authClient = createNovaAuthClient({
    baseUrl: authBaseUrl,
    fetchImpl: createFixtureFetch({
      [verifyUrl]: {
        status: 200,
        body: verifySuccessFixture,
        assertRequest: ({ init }) => {
          assert(init?.method === "POST", "verify_token must use POST");
          const headers = new Headers(init?.headers);
          assert(
            headers.get("authorization") === "Bearer integration-token",
            "verify_token must use resolved authorization header",
          );
          assert(
            headers.get("content-type")?.startsWith("application/json") ?? false,
            "verify_token must use application/json content type",
          );
          assert(
            bodyToString(init?.body) ===
              JSON.stringify({
                access_token: "integration-token",
                required_permissions: [],
                required_scopes: [],
              }),
            "verify_token must send JSON request body",
          );
        },
      },
    }),
    resolveHeaders: ({ operation }) =>
      operation.operationId === "verify_token"
        ? { authorization: "Bearer integration-token" }
        : undefined,
  });
  assert(
    authClient.baseUrl === "https://auth.nova.example",
    "auth client baseUrl must be normalized",
  );

  const verifyResult = await authClient.verify_token({
    body: {
      access_token: "integration-token",
      required_permissions: [],
      required_scopes: [],
    },
  });
  assert(verifyResult.ok, "verify_token success fixture must be ok");
  assertAuthOkResponse("verify_token", verifyResult);
  const principal = asRecord(verifyResult.data?.principal);
  assert(typeof principal.subject === "string", "principal.subject required");
  assert(Array.isArray(principal.scopes), "principal.scopes required");

  const authFailureClient = createNovaAuthClient({
    baseUrl: authBaseUrl,
    fetchImpl: createFixtureFetch({
      [verifyUrl]: {
        status: 401,
        body: verify401Fixture,
      },
    }),
  });
  const verify401 = await authFailureClient.verify_token({
    body: {
      access_token: "bad-token",
      required_permissions: [],
      required_scopes: [],
    },
  });
  assert(!verify401.ok, "verify_token 401 fixture must not be ok");
  assertErrorEnvelope(asRecord(verify401.data).error, "invalid_token");
  let sawAuthHttpError = false;
  try {
    assertAuthOkResponse("verify_token", verify401);
  } catch (error) {
    sawAuthHttpError = error instanceof NovaAuthSdkHttpError;
  }
  assert(sawAuthHttpError, "assertAuthOkResponse must throw NovaSdkHttpError");

  const authForbiddenClient = createNovaAuthClient({
    baseUrl: authBaseUrl,
    fetchImpl: createFixtureFetch({
      [verifyUrl]: {
        status: 403,
        body: verify403Fixture,
        assertRequest: ({ init }) => {
          assert(init?.method === "POST", "verify_token 403 must use POST");
          const headers = new Headers(init?.headers);
          assert(
            headers.get("authorization") === "Bearer integration-token",
            "verify_token 403 must use resolved authorization header",
          );
          assert(
            headers.get("content-type")?.startsWith("application/json") ?? false,
            "verify_token 403 must use application/json content type",
          );
          assert(
            bodyToString(init?.body) ===
              JSON.stringify({
                access_token: "insufficient-token",
                required_permissions: [],
                required_scopes: [],
              }),
            "verify_token 403 must send JSON request body",
          );
        },
      },
    }),
    resolveHeaders: ({ operation }) =>
      operation.operationId === "verify_token"
        ? { authorization: "Bearer integration-token" }
        : undefined,
  });
  const verify403Result = await authForbiddenClient.verify_token({
    body: {
      access_token: "insufficient-token",
      required_permissions: [],
      required_scopes: [],
    },
  });
  assert(!verify403Result.ok, "verify_token 403 fixture must not be ok");
  assertErrorEnvelope(asRecord(verify403Result.data).error, "insufficient_scope");
  let sawAuthForbiddenHttpError = false;
  try {
    assertAuthOkResponse("verify_token", verify403Result);
  } catch (error) {
    sawAuthForbiddenHttpError = error instanceof NovaAuthSdkHttpError;
  }
  assert(sawAuthForbiddenHttpError, "assertAuthOkResponse must throw NovaSdkHttpError");

  const introspectUrl = buildOperationDescriptorUrl(
    authBaseUrl,
    authOperations.introspect_token,
  );
  const introspectSuccessFixture = {
    active: true,
    principal: {
      subject: "subject",
      scope_id: "scope",
      tenant_id: null,
      scopes: [],
      permissions: [],
    },
    claims: { sub: "subject" },
  };
  const authIntrospectionClient = createNovaAuthClient({
    baseUrl: authBaseUrl,
    fetchImpl: createFixtureFetch({
      [introspectUrl]: {
        status: 200,
        body: introspectSuccessFixture,
        assertRequest: ({ init }) => {
          assert(init?.method === "POST", "introspect_token must use POST");
          const headers = new Headers(init?.headers);
          assert(
            headers.get("content-type") === "application/x-www-form-urlencoded",
            "introspect_token form mode must use form content type",
          );
          assert(
            bodyToString(init?.body) === "access_token=form-token&required_scopes=read",
            "introspect_token form mode must serialize as URL encoded payload",
          );
        },
      },
    }),
  });
  const introspectFormResult = await authIntrospectionClient.introspect_token({
    contentType: "application/x-www-form-urlencoded",
    body: {
      access_token: "form-token",
      required_permissions: [],
      required_scopes: ["read"],
    },
  });
  assert(introspectFormResult.ok, "introspect_token form fixture must be ok");
  assertAuthOkResponse("introspect_token", introspectFormResult);
  assert(
    introspectFormResult.data?.active === true,
    "introspection form result must report active",
  );

  const authIntrospectionJsonClient = createNovaAuthClient({
    baseUrl: authBaseUrl,
    fetchImpl: createFixtureFetch({
      [introspectUrl]: {
        status: 200,
        body: introspectSuccessFixture,
        assertRequest: ({ init }) => {
          const headers = new Headers(init?.headers);
          assert(
            headers.get("content-type") === "application/json",
            "introspect_token json mode must use JSON content type",
          );
          assert(
            bodyToString(init?.body)
              === JSON.stringify({
                access_token: "json-token",
                required_permissions: [],
                required_scopes: [],
              }),
            "introspect_token json mode must serialize as JSON payload",
          );
        },
      },
    }),
  });
  const introspectJsonResult = await authIntrospectionJsonClient.introspect_token({
    contentType: "application/json",
    body: {
      access_token: "json-token",
      required_permissions: [],
      required_scopes: [],
    },
  });
  assert(introspectJsonResult.ok, "introspect_token json fixture must be ok");
  assertAuthOkResponse("introspect_token", introspectJsonResult);

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
  const planResourcesUrl = buildOperationDescriptorUrl(
    fileBaseUrl,
    fileOperations.plan_resources,
  );
  const capabilitiesUrl = buildOperationDescriptorUrl(
    fileBaseUrl,
    fileOperations.get_capabilities,
  );
  const releaseInfoUrl = buildOperationDescriptorUrl(
    fileBaseUrl,
    fileOperations.get_release_info,
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
        status: 200,
        body: enqueueSuccessFixture,
        assertRequest: ({ init }) => {
          assert(init?.method === "POST", "create_job must use POST");
          const headers = new Headers(init?.headers);
          assert(
            headers.get("idempotency-key") === "job-123",
            "create_job must send explicit idempotency header",
          );
          assert(
            headers.get("content-type")?.startsWith("application/json") ?? false,
            "create_job must use application/json content type",
          );
          assert(
            bodyToString(init?.body) === JSON.stringify(enqueueRequestFixture),
            "create_job must send declared JSON request body",
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
            "initiate_upload must send declared JSON request body",
          );
        },
      },
      [planResourcesUrl]: {
        status: 200,
        body: planFixture,
        assertRequest: ({ init }) => {
          assert(init?.method === "POST", "plan_resources must use POST");
          const headers = new Headers(init?.headers);
          assert(
            headers.get("content-type")?.startsWith("application/json") ?? false,
            "plan_resources must use application/json content type",
          );
          assert(
            bodyToString(init?.body) === JSON.stringify({ resources: ["v1"] }),
            "plan_resources must send declared JSON request body",
          );
        },
      },
      [capabilitiesUrl]: {
        status: 200,
        body: capabilitiesFixture,
      },
      [releaseInfoUrl]: {
        status: 200,
        body: releaseFixture,
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
  assertFileOkResponse("get_job_status", jobStatusResult);
  assert(
    typeof jobStatusResult.data.job.job_id === "string",
    "job.job_id required",
  );

  const createJobResult = await fileClient.create_job({
    headers: { "Idempotency-Key": "job-123" },
    body: enqueueRequestFixture,
  });
  assertFileOkResponse("create_job", createJobResult);
  assert(typeof createJobResult.data.job_id === "string", "enqueued job_id required");

  const initiateUploadResult = await fileClient.initiate_upload({
    body: transferRequestFixture,
  });
  assertFileOkResponse("initiate_upload", initiateUploadResult);
  assert(
    typeof initiateUploadResult.data.key === "string",
    "upload key required",
  );

  const capabilitiesResult = await fileClient.get_capabilities();
  assertFileOkResponse("get_capabilities", capabilitiesResult);
  assert(
    Array.isArray(capabilitiesResult.data.capabilities),
    "capabilities list required",
  );

  const releaseInfoResult = await fileClient.get_release_info();
  assertFileOkResponse("get_release_info", releaseInfoResult);
  assert(typeof releaseInfoResult.data.version === "string", "version required");
  assert(typeof releaseInfoResult.data.name === "string", "name required");
  assert(
    typeof releaseInfoResult.data.environment === "string",
    "environment required",
  );

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
  assert(!queueUnavailableResult.ok, "queue unavailable fixture must not be ok");
  assertErrorEnvelope(asRecord(queueUnavailableResult.data).error, "queue_unavailable");
  let sawFileHttpError = false;
  try {
    assertFileOkResponse("create_job", queueUnavailableResult);
  } catch (error) {
    sawFileHttpError = error instanceof NovaFileSdkHttpError;
  }
  assert(sawFileHttpError, "assertFileOkResponse must throw NovaSdkHttpError");

  const planResult = await fileClient.plan_resources({
    body: {
      resources: ["v1"],
    },
  });
  assert(planResult.ok, "plan_resources success fixture must be ok");
  assertFileOkResponse("plan_resources", planResult);
  assert(Array.isArray(planResult.data.plan), "resource plan list required");
  assert(
    !Object.prototype.hasOwnProperty.call(fileOperations, "update_job_result"),
    "internal update_job_result operation must be excluded from public SDK",
  );

  console.log("typescript v1 conformance lane passed");
}

await main();
