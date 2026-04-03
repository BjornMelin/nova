# Release Version Manifest

Date: 2026-04-03T06:10:53+00:00
Status: Active
Schema: 1.0

## Release Metadata
- `base_commit`: `7a24bce04c0045a163b9724fa9ec0c9daf029a97`
- `head_commit`: `63659243f680693793cf902870b76277dea5d026`
- `first_release`: `False`
- `global_bump`: `patch`

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
| `infra/nova_cdk` | `nova-cdk` | `0.1.3` | yes |
| `packages/nova_dash_bridge` | `nova-dash-bridge` | `0.3.2` | no |
| `packages/nova_file_api` | `nova-file-api` | `0.5.1` | no |
| `packages/nova_runtime_support` | `nova-runtime-support` | `0.1.0` | no |
| `packages/nova_sdk_py` | `nova-sdk-py` | `1.0.0` | no |
| `packages/nova_sdk_r` | `nova` | `0.1.0` | no |
| `packages/nova_sdk_ts` | `@nova/sdk` | `0.1.0` | no |
| `packages/nova_workflows` | `nova-workflows` | `0.1.0` | no |
