# `@nova/sdk`

Generated public TypeScript SDK derived from the committed Nova file API
OpenAPI contract.

Subpath exports (no package-root barrel):

- `@nova/sdk/client`
- `@nova/sdk/sdk`
- `@nova/sdk/types`

`@nova/sdk/client` exposes the generator-owned Hey API fetch client instance.
`@nova/sdk/sdk` exposes the generated operation functions.
`@nova/sdk/types` exposes the generated public request/response and schema
types.

The package does not ship Zod or bundled runtime validation helpers, and it
does not retain a bespoke Nova transport/runtime package.
