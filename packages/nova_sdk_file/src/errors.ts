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

export class NovaSdkHttpError<TError = unknown> extends Error {
  readonly operationId: string;
  readonly response: Response;
  readonly error: TError;

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

export function assertOkResponse<TData, TError>(
  operationId: string,
  response: HttpResultLike<TData, TError>,
): asserts response is Extract<HttpResultLike<TData, TError>, { data: TData }> {
  if (response.error !== undefined) {
    throw new NovaSdkHttpError(operationId, response.response, response.error);
  }
}
