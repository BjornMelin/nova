/**
 * Static metadata describing a generated SDK operation.
 */
export interface OperationDescriptor {
  readonly operationId: string;
  readonly method: string;
  readonly path: string;
  readonly summary?: string;
}

/**
 * Allowed scalar value types for query-string fields.
 */
export type QueryValue = string | number | boolean | null | undefined;
/**
 * Query-string input map keyed by parameter name.
 */
export type QueryParams = Record<string, QueryValue>;
/**
 * Path-token replacement input map keyed by token name.
 */
export type PathParams = Record<string, string | number>;

/**
 * Runtime configuration for a JSON fetch client.
 */
export interface JsonFetchClientOptions {
  readonly baseUrl: string;
  readonly defaultHeaders?: HeadersInit;
  readonly fetchImpl?: typeof fetch;
}

/**
 * Per-request options for an SDK operation invocation.
 */
export interface JsonFetchRequestOptions {
  readonly body?: unknown;
  readonly query?: QueryParams;
  readonly pathParams?: PathParams;
  readonly headers?: HeadersInit;
  readonly signal?: AbortSignal;
}

/**
 * Normalized HTTP response payload for SDK consumers.
 */
export interface JsonFetchResponse<TData> {
  readonly status: number;
  readonly ok: boolean;
  readonly headers: Headers;
  readonly data: TData | null;
}

/**
 * JSON fetch client contract used by generated SDK call sites.
 */
export interface JsonFetchClient {
  /**
   * Execute a generated operation request and decode JSON response bodies.
   */
  request<TData>(
    operation: OperationDescriptor,
    request?: JsonFetchRequestOptions,
  ): Promise<JsonFetchResponse<TData>>;
}

/**
 * Remove trailing slash characters from a base URL.
 */
export function normalizeBaseUrl(baseUrl: string): string {
  return baseUrl.replace(/\/+$/, "");
}

function assertNoUnresolvedPathTokens(pathTemplate: string, resolvedPath: string): void {
  const unresolved = resolvedPath.match(/\{[^/{}]+\}/g);
  if (!unresolved) {
    return;
  }
  const uniqueTokens = [...new Set(unresolved)];
  throw new Error(
    `Unresolved path token(s) ${uniqueTokens.join(", ")} in path template: ${pathTemplate}`,
  );
}

/**
 * Build an absolute operation URL from a path template and request params.
 */
export function buildOperationUrl(
  baseUrl: string,
  pathTemplate: string,
  pathParams: PathParams = {},
  query: QueryParams = {},
): string {
  let resolvedPath = pathTemplate;
  for (const [key, value] of Object.entries(pathParams)) {
    resolvedPath = resolvedPath.replaceAll(
      `{${key}}`,
      encodeURIComponent(String(value)),
    );
  }
  assertNoUnresolvedPathTokens(pathTemplate, resolvedPath);

  const url = new URL(`${normalizeBaseUrl(baseUrl)}${resolvedPath}`);
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null) {
      continue;
    }
    url.searchParams.set(key, String(value));
  }
  return url.toString();
}

/**
 * Build an operation URL using a generated operation descriptor.
 */
export function buildOperationDescriptorUrl(
  baseUrl: string,
  operation: OperationDescriptor,
  pathParams: PathParams = {},
  query: QueryParams = {},
): string {
  return buildOperationUrl(baseUrl, operation.path, pathParams, query);
}

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
