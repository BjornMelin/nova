import type {
  FetchClient,
  FetchClientOptions,
  FetchRequestOptions,
  FetchResponse,
  OperationDescriptor,
} from "./contracts.js";
import { buildOperationDescriptorUrl, normalizeBaseUrl } from "./url.js";

const DEFAULT_JSON_MEDIA_TYPE = "application/json";
const FORM_URLENCODED_MEDIA_TYPE = "application/x-www-form-urlencoded";

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
  resolvedHeaders: HeadersInit | undefined,
  requestHeaders: HeadersInit | undefined,
  hasBody: boolean,
  contentType: string | undefined,
): Headers {
  const headers = new Headers(defaultHeaders);
  new Headers(resolvedHeaders).forEach((value, key) => {
    headers.set(key, value);
  });
  new Headers(requestHeaders).forEach((value, key) => {
    headers.set(key, value);
  });
  if (!headers.has("accept")) {
    headers.set("accept", DEFAULT_JSON_MEDIA_TYPE);
  }
  if (hasBody && contentType !== undefined) {
    headers.set("content-type", contentType);
  } else if (hasBody && !headers.has("content-type")) {
    headers.set("content-type", DEFAULT_JSON_MEDIA_TYPE);
  }
  return headers;
}

function encodeFormUrlEncoded(body: unknown): URLSearchParams {
  if (body instanceof URLSearchParams) {
    return body;
  }
  if (body === null || typeof body !== "object" || Array.isArray(body)) {
    throw new TypeError(
      "application/x-www-form-urlencoded request bodies must be objects or URLSearchParams",
    );
  }

  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(body)) {
    if (value === undefined) {
      continue;
    }
    if (Array.isArray(value)) {
      for (const entry of value) {
        if (entry !== undefined) {
          params.append(key, String(entry));
        }
      }
      continue;
    }
    params.append(key, String(value));
  }
  return params;
}

function encodeRequestBody(
  body: unknown,
  contentType: string | undefined,
): BodyInit | undefined {
  if (body === undefined) {
    return undefined;
  }
  if (
    contentType === undefined
    || contentType === DEFAULT_JSON_MEDIA_TYPE
    || contentType.endsWith("+json")
  ) {
    return JSON.stringify(body);
  }
  if (contentType === FORM_URLENCODED_MEDIA_TYPE) {
    return encodeFormUrlEncoded(body);
  }
  if (
    typeof body === "string"
    || body instanceof Blob
    || body instanceof FormData
    || body instanceof URLSearchParams
    || body instanceof ArrayBuffer
  ) {
    return body;
  }
  throw new TypeError(
    `unsupported request body for content type ${contentType}`,
  );
}

/**
 * Create a fetch client used by generated SDK packages.
 *
 * @param options - Runtime options used to configure the fetch client.
 * @returns Fetch client for generated operation execution.
 */
export function createFetchClient(options: FetchClientOptions): FetchClient {
  const baseUrl = normalizeBaseUrl(options.baseUrl);
  const fetchImpl = options.fetchImpl ?? globalThis.fetch.bind(globalThis);

  return {
    async request<TData>(
      operation: OperationDescriptor,
      request: FetchRequestOptions = {},
    ): Promise<FetchResponse<TData>> {
      const hasBody = request.body !== undefined;
      const contentType = hasBody
        ? request.contentType ?? DEFAULT_JSON_MEDIA_TYPE
        : undefined;
      const resolvedHeaders = await options.resolveHeaders?.({
        operation,
        request,
      });
      const response = await fetchImpl(
        buildOperationDescriptorUrl(
          baseUrl,
          operation,
          request.pathParams ?? {},
          request.query ?? {},
        ),
        {
          method: operation.method,
          headers: mergeRequestHeaders(
            options.defaultHeaders,
            resolvedHeaders,
            request.headers,
            hasBody,
            contentType,
          ),
          body: encodeRequestBody(request.body, contentType),
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
