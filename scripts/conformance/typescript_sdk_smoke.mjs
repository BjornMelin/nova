import assert from "node:assert/strict";

const expectedPackages = new Set(
  JSON.parse(process.env.NOVA_EXPECTED_NPM_PACKAGES ?? "[]"),
);
const requireTsSdk = expectedPackages.size === 0 || expectedPackages.has("@nova/sdk");

let sdkModule = null;
let clientModule = null;

try {
  sdkModule = await import("@nova/sdk/sdk");
  clientModule = await import("@nova/sdk/client");
} catch (error) {
  if (requireTsSdk) {
    throw error;
  }
}

if (requireTsSdk && (!sdkModule || !clientModule)) {
  throw new Error("@nova/sdk smoke import did not load expected entrypoints");
}

if (sdkModule) {
  if (!sdkModule.getExport) {
    throw new Error("missing expected SDK function: getExport");
  }
  if ("updateJobResult" in sdkModule) {
    throw new Error("internal file operation leaked into published SDK");
  }
}

if (clientModule && sdkModule) {
  const { client } = clientModule;
  const { getExport } = sdkModule;

  client.setConfig({
    auth: async () => "test-token",
    baseUrl: "https://nova.example/",
    fetch: async (input) => {
      const url = input.url;
      if (url !== "https://nova.example/v1/exports/export-123") {
        throw new Error(`unexpected SDK request URL: ${url}`);
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

  const response = await getExport({
    path: { export_id: "export-123" },
  });
  if (response.error) {
    throw new Error("unexpected SDK response error");
  }
  assert.equal(
    response.data?.export_id,
    "export-123",
    "SDK contract changed: expected data.export_id",
  );
  assert.equal(
    response.data?.output?.key,
    "exports/scope-1/export-123/source.csv",
    "SDK contract changed: expected data.output.key",
  );
}
