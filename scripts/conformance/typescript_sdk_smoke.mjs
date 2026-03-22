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

if (fileOperations && fileOperations.get_job_status.path !== "/v1/jobs/{job_id}") {
  throw new Error(`unexpected job-status path: ${fileOperations.get_job_status.path}`);
}

if ("update_job_result" in (fileOperations ?? {})) {
  throw new Error("internal file operation leaked into published SDK");
}

if (createFileClient && fileOperations) {
  const fileClient = createFileClient({
    baseUrl: "https://nova.example/",
    fetch: async (input) => {
      const url = input.url;
      if (url !== "https://nova.example/v1/jobs/job-123") {
        throw new Error(`unexpected file client URL: ${url}`);
      }
      return new Response(
        JSON.stringify({
          job: {
            job_id: "job-123",
            status: "queued",
            created_at: "2026-03-09T00:00:00Z",
            updated_at: "2026-03-09T00:00:00Z",
            events: [],
          },
        }),
        {
          status: 200,
          headers: { "content-type": "application/json" },
        },
      );
    },
  });
  const fileResponse = await fileClient.GET(fileOperations.get_job_status.path, {
    params: { path: { job_id: "job-123" } },
  });
  if (fileResponse.error || fileResponse.data?.job?.job_id !== "job-123") {
    throw new Error("unexpected file client response");
  }
}
