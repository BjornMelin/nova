import createClient, {
  removeTrailingSlash,
  type Client,
  type ClientOptions,
  type Middleware,
} from "openapi-fetch";

import type { paths } from "./generated/openapi.js";

export type NovaFileClient = Client<paths>;
export type NovaFileClientMiddleware = Middleware;

export interface NovaFileClientOptions
  extends Omit<ClientOptions, "baseUrl"> {
  readonly baseUrl: string;
  readonly middleware?: readonly Middleware[];
}

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
