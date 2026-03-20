"""Canonical repo-root-relative paths for release documentation artifacts.

Narrative operator runbooks live under docs/runbooks/release/.
Machine-stable files here are consumed by release automation and CI.
"""

from __future__ import annotations

# RELEASE-VERSION-MANIFEST and generated runtime config markdown live here.
RELEASE_ARTIFACTS_DIR = "docs/release"

RELEASE_VERSION_MANIFEST_PATH = (
    f"{RELEASE_ARTIFACTS_DIR}/RELEASE-VERSION-MANIFEST.md"
)

RUNTIME_CONFIG_GENERATED_MD_PATH = (
    f"{RELEASE_ARTIFACTS_DIR}/runtime-config-contract.generated.md"
)
