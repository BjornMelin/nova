#!/usr/bin/env bash
set -euo pipefail

usage="usage: verify_r_cmd_check.sh <package-dir> [--keep-tarball]"
package_dir="${1:?${usage}}"
keep_tarball=false

if [[ $# -gt 1 ]]; then
  case "${2}" in
    --keep-tarball)
      keep_tarball=true
      ;;
    *)
      echo "${usage}" >&2
      exit 1
      ;;
  esac
fi

if [[ $# -gt 2 ]]; then
  echo "${usage}" >&2
  exit 1
fi

if ! command -v R >/dev/null 2>&1; then
  echo "R is required for SDK conformance checks." >&2
  exit 1
fi

repo_root="$(pwd -P)"
case "${package_dir}" in
  /*) package_dir_abs="${package_dir}" ;;
  *) package_dir_abs="${repo_root}/${package_dir}" ;;
esac

if [[ ! -d "${package_dir_abs}" ]]; then
  echo "Package directory not found: ${package_dir}" >&2
  exit 1
fi

package_name="$(
  sed -n 's/^Package: //p' "${package_dir_abs}/DESCRIPTION" | head -n 1
)"
if [[ -z "${package_name}" ]]; then
  echo "${package_dir_abs}/DESCRIPTION is missing a Package field" >&2
  exit 1
fi

tmp_dir="$(mktemp -d)"
cleanup() {
  rm -rf "${tmp_dir}"
}
trap cleanup EXIT

work_package_dir="${tmp_dir}/$(basename "${package_dir_abs}")"
cp -R "${package_dir_abs}" "${work_package_dir}"
cd "${tmp_dir}"

R CMD build "${work_package_dir}"
tarball="$(
  find . -maxdepth 1 -name "${package_name}_*.tar.gz" -print | sort | tail -n 1
)"
if [[ -z "${tarball}" ]]; then
  echo "Unable to locate built tarball for ${package_name}" >&2
  exit 1
fi

# CI and release runners should not need a TeX toolchain just to validate the
# generated SDK package. Keep the warning/error gate, but skip PDF manual build.
R CMD check --no-manual "${tarball}"

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

if [[ "${keep_tarball}" == true ]]; then
  cp -f "${tarball}" "${repo_root}/"
fi
