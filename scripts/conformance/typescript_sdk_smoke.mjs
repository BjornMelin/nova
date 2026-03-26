import assert from "node:assert/strict";

const expectedPackages = new Set(
  JSON.parse(process.env.NOVA_EXPECTED_NPM_PACKAGES ?? "[]"),
);
const requireFileSdk =
  expectedPackages.size === 0 || expectedPackages.has("@nova/sdk-file");

let fileOperations = null;
let createFileClient = null;

try {
  ({ operations: fileOperations } = await import("@nova/sdk-file/operations"));
  ({ createNovaFileClient: createFileClient } = await import(
    "@nova/sdk-file/client"
  ));
} catch (error) {
  if (requireFileSdk) {
    throw error;
  }
}

if (requireFileSdk && (!fileOperations || !createFileClient)) {
  throw new Error("@nova/sdk-file smoke import did not load expected entrypoints");
}

if (
  fileOperations &&
  fileOperations.get_export.path !== "/v1/exports/{export_id}"
) {
  throw new Error(
    `unexpected export path: ${fileOperations.get_export.path}`,
  );
}

if ("update_job_result" in (fileOperations ?? {})) {
  throw new Error("internal file operation leaked into published SDK");
}

if (createFileClient && fileOperations) {
  const fileClient = createFileClient({
    baseUrl: "https://nova.example/",
    fetch: async (input) => {
      const url = input.url;
      if (url !== "https://nova.example/v1/exports/export-123") {
        throw new Error(`unexpected file client URL: ${url}`);
      }
      return new Response(
        JSON.stringify({
          export_id: "export-123",
          source_key: "uploads/scope-1/source.csv",
          filename: "source.csv",
          status: "queued",
          output: {
            key: "exports/scope-1/export-123/source.csv",
            download_filename: "source.csv",
          },
          error: null,
          created_at: "2026-03-09T00:00:00Z",
          updated_at: "2026-03-09T00:00:00Z",
        }),
        {
          status: 200,
          headers: { "content-type": "application/json" },
        },
      );
    },
  });
  const fileResponse = await fileClient.GET(fileOperations.get_export.path, {
    params: { path: { export_id: "export-123" } },
  });
  if (fileResponse.error) {
    throw new Error("unexpected file client response error");
  }
  assert.equal(
    fileResponse.data?.export_id,
    "export-123",
    "SDK contract changed: expected data.export_id",
  );
  assert.equal(
    fileResponse.data?.output?.key,
    "exports/scope-1/export-123/source.csv",
    "SDK contract changed: expected data.output.key",
  );
}
