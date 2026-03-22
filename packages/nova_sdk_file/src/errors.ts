interface HttpErrorResult<TError = unknown> {
  readonly data?: never;
  readonly error: TError;
  readonly response: Response;
}

type HttpResultLike<TData = unknown, TError = unknown> =
  | {
      readonly data: TData;
      readonly error?: never;
      readonly response: Response;
    }
  | HttpErrorResult<TError>;

/**
 * Error thrown when an SDK call returns a non-success HTTP result.
 *
 * @typeParam TError - OpenAPI-typed error payload carried in the response.
 */
export class NovaSdkHttpError<TError = unknown> extends Error {
  readonly operationId: string;
  readonly response: Response;
  readonly error: TError;

  /**
   * @param operationId - Stable operation identifier for the failed request.
   * @param response - Raw HTTP response returned by the transport.
   * @param error - OpenAPI-typed error payload from the response body.
   */
  constructor(operationId: string, response: Response, error: TError) {
    super(`HTTP ${response.status} for ${operationId}`);
    this.name = "NovaSdkHttpError";
    this.operationId = operationId;
    this.response = response;
    this.error = error;
  }

  get status(): number {
    return this.response.status;
  }

  get data(): TError {
    return this.error;
  }

  get headers(): Headers {
    return this.response.headers;
  }
}

/**
 * Assert an `openapi-fetch` result is successful and throw otherwise.
 *
 * @typeParam TData - Success payload type for the result.
 * @typeParam TError - Error payload type for the result.
 * @param operationId - Stable operation identifier for error reporting.
 * @param response - Result union returned by an SDK request.
 * @returns The same response narrowed to the success arm.
 * @throws {NovaSdkHttpError<TError>} When the response contains an error arm.
 */
export function assertOkResponse<TData, TError>(
  operationId: string,
  response: HttpResultLike<TData, TError>,
): asserts response is Extract<HttpResultLike<TData, TError>, { data: TData }> {
  if ("error" in response) {
    throw new NovaSdkHttpError(operationId, response.response, response.error);
  }
}
