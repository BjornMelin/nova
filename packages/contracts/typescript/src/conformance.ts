import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { client } from "@nova/sdk/client";
import {
  cancelExport,
  createExport,
  getCapabilities,
  getExport,
  getReleaseInfo,
  initiateUpload,
  listExports,
  planResources,
} from "@nova/sdk/sdk";
import type {
  CreateExportData,
  InitiateUploadData,
} from "@nova/sdk/types";

type JsonRecord = Record<string, unknown>;

interface Manifest {
  fixtures: {
    transfer: {
      initiate_request: string;
      initiate_success: string;
    };
    exports: {
      create_request: string;
      create_success: string;
      get_success: string;
      list_success: string;
      cancel_success: string;
      create_503_queue_unavailable: string;
    };
    v1api: {
      capabilities_success: string;
      resources_plan_success: string;
      releases_info_success: string;
    };
  };
}

interface ErrorEnvelope {
  error: {
    code: string;
    details: JsonRecord;
    message: string;
    request_id: string | null;
  };
}

interface MockResponseFixture {
  readonly status: number;
  readonly body: unknown;
  readonly assertRequest?: (request: Request) => Promise<void> | void;
}

type AssertFalse<T extends false> = T;
type SdkTypeModule = typeof import("@nova/sdk/types");
type SdkModule = typeof import("@nova/sdk/sdk");

type _NoRawTypesComponentsExport = AssertFalse<
  "Components" extends keyof SdkTypeModule ? true : false
>;
type _NoRawTypesPathsExport = AssertFalse<
  "Paths" extends keyof SdkTypeModule ? true : false
>;
type _NoRawTypesOperationsExport = AssertFalse<
  "Operations" extends keyof SdkTypeModule ? true : false
>;
type _NoRawTypesOperationIdExport = AssertFalse<
  "OperationId" extends keyof SdkTypeModule ? true : false
>;
type _NoInternalJobResultRequestExport = AssertFalse<
  "JobResultUpdateRequest" extends keyof SdkTypeModule ? true : false
>;
type _NoInternalJobResultResponseExport = AssertFalse<
  "JobResultUpdateResponse" extends keyof SdkTypeModule ? true : false
>;
type _NoInternalUpdateJobResultOperation = AssertFalse<
  "updateJobResult" extends keyof SdkModule ? true : false
>;

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
  const envelope = asRecord(value) as unknown as ErrorEnvelope;
  assert(Boolean(envelope.error), "error envelope must include error");
  assert(envelope.error.code === code, `error.code must be ${code}`);
  assert(Boolean(envelope.error.message), "error.message required");
  assert(Boolean(envelope.error.request_id), "error.request_id required");
}

async function requestBodyText(request: Request): Promise<string> {
  return request.text();
}

function createFixtureFetch(
  routes: Record<string, MockResponseFixture | MockResponseFixture[]>,
): typeof fetch {
  return async (input) => {
    const request =
      input instanceof Request ? input : new Request(input);
    const route =
      routes[`${request.method} ${request.url}`] ?? routes[request.url];
    if (!route) {
      throw new Error(`unexpected request URL: ${request.url}`);
    }
    const fixture = Array.isArray(route) ? route.shift() : route;
    if (!fixture) {
      throw new Error(`unexpected request URL: ${request.url}`);
    }
    await fixture.assertRequest?.(request);
    return new Response(JSON.stringify(fixture.body), {
      status: fixture.status,
      headers: { "content-type": "application/json" },
    });
  };
}

async function main(): Promise<void> {
  const manifest = readJson<Manifest>("manifest.json");

  const transferRequestFixture = readJson<InitiateUploadData["body"]>(
    manifest.fixtures.transfer.initiate_request,
  );
  const transferSuccessFixture = readJson<unknown>(
    manifest.fixtures.transfer.initiate_success,
  );
  const createExportRequestFixture = readJson<CreateExportData["body"]>(
    manifest.fixtures.exports.create_request,
  );
  const createExportSuccessFixture = readJson<unknown>(
    manifest.fixtures.exports.create_success,
  );
  const cancelExportSuccessFixture = readJson<unknown>(
    manifest.fixtures.exports.cancel_success,
  );
  const queueUnavailableFixture = readJson<unknown>(
    manifest.fixtures.exports.create_503_queue_unavailable,
  );
  const getExportSuccessFixture = readJson<unknown>(
    manifest.fixtures.exports.get_success,
  );
  const listExportSuccessFixture = readJson<unknown>(
    manifest.fixtures.exports.list_success,
  );
  const capabilitiesFixture = readJson<unknown>(
    manifest.fixtures.v1api.capabilities_success,
  );
  const planFixture = readJson<unknown>(
    manifest.fixtures.v1api.resources_plan_success,
  );
  const expectedPlanPayload = {
    resources: ["exports", "transfers"],
  };
  const releaseFixture = readJson<unknown>(
    manifest.fixtures.v1api.releases_info_success,
  );

  const fileBaseUrl = "https://file.nova.example/";
  const getExportUrl = "https://file.nova.example/v1/exports/export-123";
  const createExportUrl = "https://file.nova.example/v1/exports";
  const listExportUrl = "https://file.nova.example/v1/exports";
  const cancelExportUrl =
    "https://file.nova.example/v1/exports/export-123/cancel";
  const initiateUploadUrl =
    "https://file.nova.example/v1/transfers/uploads/initiate";
  const capabilitiesUrl = "https://file.nova.example/v1/capabilities";
  const planUrl = "https://file.nova.example/v1/resources/plan";
  const releaseUrl = "https://file.nova.example/v1/releases/info";

  client.setConfig({
    auth: async () => "test-token",
    baseUrl: fileBaseUrl,
    fetch: createFixtureFetch({
      [getExportUrl]: {
        status: 200,
        body: getExportSuccessFixture,
        assertRequest: (request) => {
          assert(request.method === "GET", "getExport must use GET");
          assert(
            request.headers.get("authorization") === "Bearer test-token",
            "auth config must inject authorization header",
          );
          assert(
            request.headers.get("x-request-id") === "req-123",
            "request interceptor must inject request id header",
          );
        },
      },
      [`POST ${createExportUrl}`]: [
        {
          status: 201,
          body: createExportSuccessFixture,
          assertRequest: async (request) => {
            assert(request.method === "POST", "createExport must use POST");
            assert(
              request.headers.get("content-type")?.startsWith("application/json") ??
                false,
              "createExport must use application/json content type",
            );
            assert(
              request.headers.get("idempotency-key") === "idem-123",
              "createExport must preserve Idempotency-Key header",
            );
            assert(
              (await requestBodyText(request)) ===
                JSON.stringify(createExportRequestFixture),
              "createExport must send JSON request body",
            );
          },
        },
        {
          status: 503,
          body: queueUnavailableFixture,
        },
      ],
      [`GET ${listExportUrl}`]: {
        status: 200,
        body: listExportSuccessFixture,
        assertRequest: (request) => {
          assert(request.method === "GET", "listExports must use GET");
        },
      },
      [`POST ${cancelExportUrl}`]: {
        status: 200,
        body: cancelExportSuccessFixture,
        assertRequest: (request) => {
          assert(request.method === "POST", "cancelExport must use POST");
        },
      },
      [initiateUploadUrl]: {
        status: 200,
        body: transferSuccessFixture,
        assertRequest: async (request) => {
          assert(request.method === "POST", "initiateUpload must use POST");
          assert(
            request.headers.get("content-type")?.startsWith("application/json") ??
              false,
            "initiateUpload must use application/json content type",
          );
          assert(
            (await requestBodyText(request)) ===
              JSON.stringify(transferRequestFixture),
            "initiateUpload must send JSON request body",
          );
        },
      },
      [capabilitiesUrl]: {
        status: 200,
        body: capabilitiesFixture,
        assertRequest: (request) => {
          assert(request.method === "GET", "getCapabilities must use GET");
        },
      },
      [planUrl]: {
        status: 200,
        body: planFixture,
        assertRequest: async (request) => {
          assert(request.method === "POST", "planResources must use POST");
          assert(
            request.headers.get("content-type")?.includes("application/json") ??
              false,
            "planResources must use application/json content type",
          );
          assert(
            JSON.stringify(JSON.parse(await requestBodyText(request))) ===
              JSON.stringify(expectedPlanPayload),
            "planResources must send JSON request body",
          );
        },
      },
      [releaseUrl]: {
        status: 200,
        body: releaseFixture,
        assertRequest: (request) => {
          assert(request.method === "GET", "getReleaseInfo must use GET");
        },
      },
    }),
  });

  client.interceptors.request.use(async (request: Request) => {
    const headers = new Headers(request.headers);
    headers.set("x-request-id", "req-123");
    return new Request(request, { headers });
  });

  const getExportResult = await getExport({
    path: { export_id: "export-123" },
  });
  assert(!getExportResult.error, "getExport should not return an error");
  assert(
    asRecord(getExportResult.data).export_id === "export-123",
    "getExport must return export_id",
  );

  const createExportResult = await createExport({
    body: createExportRequestFixture,
    headers: { "Idempotency-Key": "idem-123" },
  });
  assert(!createExportResult.error, "createExport should not return an error");

  const listExportsResult = await listExports();
  assert(!listExportsResult.error, "listExports should not return an error");
  assert(
    Array.isArray(asRecord(listExportsResult.data).exports),
    "listExports must return an exports array",
  );

  const cancelExportResult = await cancelExport({
    path: { export_id: "export-123" },
  });
  assert(
    !cancelExportResult.error,
    "cancelExport should not return an error",
  );

  const initiateUploadResult = await initiateUpload({
    body: transferRequestFixture,
  });
  assert(
    !initiateUploadResult.error,
    "initiateUpload should not return an error",
  );
  assert(
    asRecord(initiateUploadResult.data).strategy === "single",
    "initiateUpload must preserve strategy field",
  );

  const capabilitiesResult = await getCapabilities();
  assert(
    !capabilitiesResult.error,
    "getCapabilities should not return an error",
  );

  const planResourcesResult = await planResources({
    body: expectedPlanPayload,
  });
  assert(
    !planResourcesResult.error,
    "planResources should not return an error",
  );

  const releaseInfoResult = await getReleaseInfo();
  assert(
    !releaseInfoResult.error,
    "getReleaseInfo should not return an error",
  );

  const queueUnavailableResult = await createExport({
    body: createExportRequestFixture,
  });
  assert(
    Boolean(queueUnavailableResult.error),
    "createExport must surface queue_unavailable errors",
  );
  assertErrorEnvelope(queueUnavailableResult.error, "queue_unavailable");
}

await main();
