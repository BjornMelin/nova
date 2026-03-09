# `@nova/sdk-file`

Generated public file SDK derived from the committed Nova file API OpenAPI
contract.

Subpath exports (no package-root barrel):

- `@nova/sdk-file/client`
- `@nova/sdk-file/errors`
- `@nova/sdk-file/operations`
- `@nova/sdk-file/types`

The package is transport-focused and does not ship Zod or bundled runtime
validation helpers.

Public `types` exports are curated operation helpers and reachable public
schemas only; internal worker-only models are intentionally excluded even
though they remain present in the raw generated OpenAPI implementation detail.
