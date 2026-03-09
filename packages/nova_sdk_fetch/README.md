# `@nova/sdk-fetch`

Thin fetch-based runtime adapter for Nova generated TypeScript operation
catalogs.

Runtime helper contracts:

- `buildOperationUrl(baseUrl, pathTemplate, pathParams?, queryParams?)`
- `buildOperationDescriptorUrl(baseUrl, operation, pathParams?, queryParams?)`
- `createJsonFetchClient({ baseUrl, defaultHeaders?, fetchImpl? })`

Client factory:

- `createJsonFetchClient(options)` returns a JSON fetch client instance with
  `request(operation, requestOptions?)`.
- `requestOptions` supports `body`, `query`, `pathParams`, `headers`, and
  `signal`.
- The client resolves operation URLs via `buildOperationDescriptorUrl` and
  decodes JSON responses when content type is `application/json` or `*+json`.

Behavior notes:

- `buildOperationUrl` throws when a `{token}` placeholder remains unresolved
  after applying `pathParams`.
- JSON response decoding accepts both `application/json` and `application/*+json`
  media types.
