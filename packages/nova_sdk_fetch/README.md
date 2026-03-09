# `@nova/sdk-fetch`

Thin fetch-based runtime adapter for Nova generated public TypeScript SDKs.

Subpath exports (no package-root barrel):

- `@nova/sdk-fetch/url`
- `@nova/sdk-fetch/client`
- `@nova/sdk-fetch/contracts`

Runtime helper contracts (`@nova/sdk-fetch/url`):

- `buildOperationUrl(baseUrl, pathTemplate, pathParams?, queryParams?)`
- `buildOperationDescriptorUrl(baseUrl, operation, pathParams?, queryParams?)`

Client factory:

- Import from `@nova/sdk-fetch/client`.
- `createFetchClient(options)` returns a fetch client instance with
  `request(operation, requestOptions?)`.
- `requestOptions` supports `body`, `contentType`, `query`, `pathParams`,
  `headers`, and `signal`.
- `options.resolveHeaders(context)` can inject per-operation auth or request
  headers without hard-coding SDK-specific policy into the shared transport.
- The client resolves operation URLs via `buildOperationDescriptorUrl` and
  decodes JSON responses when content type is `application/json` or `*+json`.

Behavior notes:

- `buildOperationUrl` throws when a `{token}` placeholder remains unresolved
  after applying `pathParams`.
- Request-body serialization follows the resolved request `contentType`.
  Generated SDKs set single-media request types automatically and require
  explicit `contentType` selection for multi-media request bodies.
- JSON response decoding accepts both `application/json` and `application/*+json`
  media types.
