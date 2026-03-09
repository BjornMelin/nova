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
 * Runtime configuration for a generated fetch client.
 */
export interface FetchClientOptions {
  readonly baseUrl: string;
  readonly defaultHeaders?: HeadersInit;
  readonly fetchImpl?: typeof fetch;
  readonly resolveHeaders?: FetchHeadersResolver;
}

/**
 * Per-request options for an SDK operation invocation.
 */
export interface FetchRequestOptions {
  readonly body?: unknown;
  readonly contentType?: string;
  readonly query?: QueryParams;
  readonly pathParams?: PathParams;
  readonly headers?: HeadersInit;
  readonly signal?: AbortSignal;
}

/**
 * Runtime context provided to request-header resolver hooks.
 */
export interface FetchHeaderResolutionContext {
  readonly operation: OperationDescriptor;
  readonly request: FetchRequestOptions;
}

/**
 * Resolve per-request headers from runtime client context.
 */
export type FetchHeadersResolver = (
  context: FetchHeaderResolutionContext,
) => HeadersInit | undefined | Promise<HeadersInit | undefined>;

/**
 * Normalized HTTP response payload for SDK consumers.
 *
 * @typeParam TData - Expected shape of the decoded response body.
 */
export interface FetchResponse<TData> {
  readonly status: number;
  readonly ok: boolean;
  readonly headers: Headers;
  readonly data: TData | null;
}

/**
 * Fetch client contract used by generated SDK call sites.
 */
export interface FetchClient {
  /**
   * Execute a generated operation request and decode JSON response bodies.
   */
  request<TData>(
    operation: OperationDescriptor,
    request?: FetchRequestOptions,
  ): Promise<FetchResponse<TData>>;
}
