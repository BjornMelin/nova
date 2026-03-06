export interface OperationDescriptor {
  readonly operationId: string;
  readonly method: string;
  readonly path: string;
}

export type QueryValue = string | number | boolean | null | undefined;
export type QueryParams = Record<string, QueryValue>;
export type PathParams = Record<string, string | number>;

export interface JsonFetchClientOptions {
  readonly baseUrl: string;
  readonly defaultHeaders?: HeadersInit;
  readonly fetchImpl?: typeof fetch;
}

export interface JsonFetchRequestOptions {
  readonly body?: unknown;
  readonly query?: QueryParams;
  readonly pathParams?: PathParams;
  readonly headers?: HeadersInit;
  readonly signal?: AbortSignal;
}

export interface JsonFetchResponse<TData> {
  readonly status: number;
  readonly ok: boolean;
  readonly headers: Headers;
  readonly data: TData | null;
}

function normalizeBaseUrl(baseUrl: string): string {
  return baseUrl.replace(/\/+$/, "");
}

function buildUrl(
  baseUrl: string,
  operation: OperationDescriptor,
  pathParams: PathParams,
  query: QueryParams,
): string {
  let resolvedPath = operation.path;
  for (const [key, value] of Object.entries(pathParams)) {
    resolvedPath = resolvedPath.replaceAll(
      `{${key}}`,
      encodeURIComponent(String(value)),
    );
  }

  const url = new URL(`${normalizeBaseUrl(baseUrl)}${resolvedPath}`);
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null) {
      continue;
    }
    url.searchParams.set(key, String(value));
  }
  return url.toString();
}

async function decodeJsonBody<TData>(response: Response): Promise<TData | null> {
  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) {
    return null;
  }
  return (await response.json()) as TData;
}

export function createJsonFetchClient(options: JsonFetchClientOptions) {
  const baseUrl = normalizeBaseUrl(options.baseUrl);
  const defaultHeaders = options.defaultHeaders ?? {};
  const fetchImpl = options.fetchImpl ?? globalThis.fetch.bind(globalThis);

  return {
    async request<TData>(
      operation: OperationDescriptor,
      request: JsonFetchRequestOptions = {},
    ): Promise<JsonFetchResponse<TData>> {
      const response = await fetchImpl(
        buildUrl(
          baseUrl,
          operation,
          request.pathParams ?? {},
          request.query ?? {},
        ),
        {
          method: operation.method,
          headers: {
            Accept: "application/json",
            ...defaultHeaders,
            ...request.headers,
          },
          body:
            request.body === undefined
              ? undefined
              : JSON.stringify(request.body),
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
