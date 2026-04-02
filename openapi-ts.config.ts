import { defineConfig } from "@hey-api/openapi-ts";

const input =
  process.env.NOVA_OPENAPI_TS_INPUT ??
  "./packages/contracts/openapi/nova-file-api.openapi.json";
const outputPath =
  process.env.NOVA_OPENAPI_TS_OUTPUT ??
  "./packages/nova_sdk_ts/src/client";

/**
 * Hey API OpenAPI TypeScript generator configuration for Nova's SDK output.
 */
export default defineConfig({
  input,
  output: {
    entryFile: false,
    module: {
      extension: '.js',
    },
    path: outputPath,
  },
  plugins: [
    "@hey-api/typescript",
    {
      auth: true,
      name: "@hey-api/sdk",
      operations: {
        strategy: "flat",
      },
    },
    "@hey-api/client-fetch",
  ],
});
