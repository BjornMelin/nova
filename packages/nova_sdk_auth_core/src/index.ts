export interface OperationDescriptor {
  readonly operationId: string;
  readonly method: string;
  readonly path: string;
  readonly summary?: string;
}

export type PathParams = Record<string, string | number>;
export type QueryValue = string | number | boolean | null | undefined;
export type QueryParams = Record<string, QueryValue>;

export function normalizeBaseUrl(baseUrl: string): string {
  return baseUrl.replace(/\/+$/, "");
}

export function buildOperationUrl(
  baseUrl: string,
  pathTemplate: string,
  pathParams: PathParams = {},
  queryParams: QueryParams = {},
): string {
  let resolvedPath = pathTemplate;
  for (const [key, value] of Object.entries(pathParams)) {
    resolvedPath = resolvedPath.replaceAll(
      `{${key}}`,
      encodeURIComponent(String(value)),
    );
  }

  const url = new URL(`${normalizeBaseUrl(baseUrl)}${resolvedPath}`);
  for (const [key, value] of Object.entries(queryParams)) {
    if (value === undefined || value === null) {
      continue;
    }
    url.searchParams.set(key, String(value));
  }
  return url.toString();
}

export { operations, type GeneratedOperationCatalog, type OperationId } from "./generated.js";
