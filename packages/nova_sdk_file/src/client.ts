import createClient, {
  removeTrailingSlash,
  type Client,
  type ClientOptions,
  type Middleware,
} from "openapi-fetch";

import type { paths } from "./generated/openapi.js";

/** OpenAPI-fetch client instance specialized for Nova file API paths. */
export type NovaFileClient = Client<paths>;
/** Middleware shape accepted by the Nova file client. */
export type NovaFileClientMiddleware = Middleware;

/** Options used to construct a Nova file SDK client. */
export interface NovaFileClientOptions
  extends Omit<ClientOptions, "baseUrl"> {
  readonly baseUrl: string;
  readonly middleware?: readonly Middleware[];
}

/**
 * Create a Nova file SDK client backed by `openapi-fetch`.
 *
 * @param options - Client options, including `baseUrl` and optional middleware.
 * @returns A configured `Client<paths>` instance for Nova file operations.
 */
export function createNovaFileClient(
  options: NovaFileClientOptions,
): NovaFileClient {
  const { middleware = [], baseUrl, ...clientOptions } = options;
  const client = createClient<paths>({
    ...clientOptions,
    baseUrl: removeTrailingSlash(baseUrl),
  });

  if (middleware.length > 0) {
    client.use(...middleware);
  }

  return client;
}
