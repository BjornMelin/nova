# `@nova/sdk-auth`

Generated public auth SDK derived from the committed Nova auth API OpenAPI
contract.

Subpath exports (no package-root barrel):

- `@nova/sdk-auth/client`
- `@nova/sdk-auth/errors`
- `@nova/sdk-auth/operations`
- `@nova/sdk-auth/types`

The package is transport-focused and does not ship Zod or bundled runtime
validation helpers.

Public `types` exports are curated operation helpers and reachable public
schemas only; the package does not expose raw whole-spec OpenAPI aliases.

`introspect_token` retains both documented request media types. Callers choose
between JSON and `application/x-www-form-urlencoded` by setting the generated
`contentType` field on the request object.
