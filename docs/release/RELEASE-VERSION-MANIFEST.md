# Release Version Manifest

Date: 2026-03-24T20:31:26+00:00
Status: Active
Schema: 1.0

## Release Metadata

- `base_commit`: `e8eb5a3c1ec8fee6ee32a3c423a628e56597ffd8`
- `head_commit`: `e8eb5a3c1ec8fee6ee32a3c423a628e56597ffd8`
- `first_release`: `False`
- `global_bump`: `None`

## changed-units.json Schema

```json
{
  "schema_version": "1.0",
  "base_commit": "<git-commit-or-null>",
  "head_commit": "<git-commit>",
  "first_release": true,
  "changed_files": ["path/to/file.py"],
  "changed_units": [
    {
      "unit_id": "packages/nova_file_api",
      "project": "nova-file-api",
      "path": "packages/nova_file_api",
      "format": "pypi",
      "codeartifact_format": "pypi",
      "namespace": null,
      "version": "0.1.0"
    }
  ]
}
```

## Canonical Runtime Monorepo

| Unit | Package | Version | Changed |
| --- | --- | --- | --- |
| `packages/nova_dash_bridge` | `nova-dash-bridge` | `0.3.1` | no |
| `packages/nova_file_api` | `nova-file-api` | `0.5.0` | no |
| `packages/nova_runtime_support` | `nova-runtime-support` | `0.1.0` | no |
| `packages/nova_sdk_ts` | `@nova/sdk` | `0.1.0` | no |
| `packages/nova_sdk_py_file` | `nova-sdk-py-file` | `1.0.0` | no |
| `packages/nova_sdk_r_file` | `nova.sdk.r.file` | `0.1.0` | no |
