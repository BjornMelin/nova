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
