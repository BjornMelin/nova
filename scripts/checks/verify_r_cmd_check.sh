#!/usr/bin/env bash
set -euo pipefail

package_dir="${1:?usage: verify_r_cmd_check.sh <package-dir>}"

if ! command -v R >/dev/null 2>&1; then
  echo "R is required for SDK conformance checks." >&2
  exit 1
fi

package_name="$(sed -n 's/^Package: //p' "${package_dir}/DESCRIPTION" | head -n 1)"
if [[ -z "${package_name}" ]]; then
  echo "${package_dir}/DESCRIPTION is missing a Package field" >&2
  exit 1
fi

rm -f "${package_name}"_*.tar.gz
rm -rf "${package_name}.Rcheck"

R CMD build "${package_dir}"

tarball="$(find . -maxdepth 1 -name "${package_name}_*.tar.gz" -print | sort | tail -n 1)"
if [[ -z "${tarball}" ]]; then
  echo "Unable to locate built tarball for ${package_name}" >&2
  exit 1
fi

R CMD check "${tarball}"

check_log="${package_name}.Rcheck/00check.log"
if [[ ! -f "${check_log}" ]]; then
  echo "Missing R CMD check log: ${check_log}" >&2
  exit 1
fi

if grep -E '^Status: .*WARNING' "${check_log}" >/dev/null; then
  echo "R CMD check reported warnings for ${package_name}" >&2
  grep -E '^Status:' "${check_log}" >&2 || true
  exit 1
fi

rm -rf "${package_name}.Rcheck"
rm -f "${tarball}"
