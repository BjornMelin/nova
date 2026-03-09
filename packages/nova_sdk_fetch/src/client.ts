import type {
  JsonFetchClient,
  JsonFetchClientOptions,
  JsonFetchRequestOptions,
  JsonFetchResponse,
  OperationDescriptor,
} from "./contracts.js";
import { buildOperationDescriptorUrl, normalizeBaseUrl } from "./url.js";

async function decodeJsonBody<TData>(response: Response): Promise<TData | null> {
  const contentType = response.headers.get("content-type") ?? "";
  const mediaType = contentType.split(";")[0]?.trim().toLowerCase() ?? "";
  if (mediaType !== "application/json" && !mediaType.endsWith("+json")) {
    return null;
  }
  return (await response.json()) as TData;
}

function mergeRequestHeaders(
  defaultHeaders: HeadersInit | undefined,
  requestHeaders: HeadersInit | undefined,
  hasBody: boolean,
): Headers {
  const headers = new Headers(defaultHeaders);
  new Headers(requestHeaders).forEach((value, key) => headers.set(key, value));
  if (!headers.has("accept")) {
    headers.set("accept", "application/json");
  }
  if (hasBody && !headers.has("content-type")) {
    headers.set("content-type", "application/json");
  }
  return headers;
}

/**
 * Create a JSON-aware fetch client used by generated SDK packages.
 *
 * @param options Runtime options used to configure the JSON fetch client.
 * @returns JSON fetch client for generated operation execution.
 */
export function createJsonFetchClient(options: JsonFetchClientOptions): JsonFetchClient {
  const baseUrl = normalizeBaseUrl(options.baseUrl);
  const fetchImpl = options.fetchImpl ?? globalThis.fetch.bind(globalThis);

  return {
    async request<TData>(
      operation: OperationDescriptor,
      request: JsonFetchRequestOptions = {},
    ): Promise<JsonFetchResponse<TData>> {
      const hasBody = request.body !== undefined;
      const response = await fetchImpl(
        buildOperationDescriptorUrl(
          baseUrl,
          operation,
          request.pathParams ?? {},
          request.query ?? {},
        ),
        {
          method: operation.method,
          headers: mergeRequestHeaders(options.defaultHeaders, request.headers, hasBody),
          body: hasBody ? JSON.stringify(request.body) : undefined,
          signal: request.signal,
        },
      );

      return {
        status: response.status,
        ok: response.ok,
        headers: response.headers,
        data: await decodeJsonBody<TData>(response),
      };
    },
  };
}
