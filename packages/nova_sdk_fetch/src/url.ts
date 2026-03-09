import type { OperationDescriptor, PathParams, QueryParams } from "./contracts.js";

/**
 * Remove trailing slash characters from a base URL.
 *
 * @param baseUrl Base URL value to normalize.
 * @returns Normalized base URL without trailing slash characters.
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
 *
 * @param baseUrl API base URL for the operation.
 * @param pathTemplate Route path template that may contain `{token}` segments.
 * @param pathParams Replacement values keyed by path token name.
 * @param query Query-string values keyed by parameter name.
 * @returns Fully qualified operation URL string.
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
 *
 * @param baseUrl API base URL for the operation.
 * @param operation Generated operation descriptor with route metadata.
 * @param pathParams Replacement values keyed by path token name.
 * @param query Query-string values keyed by parameter name.
 * @returns Fully qualified operation URL string.
 * @throws Error when required path tokens remain unresolved after substitution.
 */
export function buildOperationDescriptorUrl(
  baseUrl: string,
  operation: OperationDescriptor,
  pathParams: PathParams = {},
  query: QueryParams = {},
): string {
  return buildOperationUrl(baseUrl, operation.path, pathParams, query);
}
