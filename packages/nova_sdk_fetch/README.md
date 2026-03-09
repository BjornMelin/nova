# `@nova/sdk-fetch`

Thin fetch-based runtime adapter for Nova generated TypeScript operation
catalogs.

Runtime helper contracts:

- `buildOperationUrl(baseUrl, pathTemplate, pathParams?, queryParams?)`
- `buildOperationDescriptorUrl(baseUrl, operation, pathParams?, queryParams?)`

Behavior notes:

- `buildOperationUrl` throws when a `{token}` placeholder remains unresolved
  after applying `pathParams`.
- JSON response decoding accepts both `application/json` and `application/*+json`
  media types.
