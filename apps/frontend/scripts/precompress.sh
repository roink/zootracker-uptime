#!/usr/bin/env bash
# Precompress built assets with brotli, gzip, and zstd.
# Usage: ./scripts/precompress.sh <build_dir>
set -euo pipefail

DIR="${1:-dist}"

if [[ ! -d "$DIR" ]]; then
  echo "Error: build directory '$DIR' does not exist" >&2
  exit 1
fi

# File globs to compress (adjust to taste)
GLOBS=(
  '*.js'
  '*.css'
  '*.html'
  '*.json'
  '*.svg'
  '*.txt'
  '*.xml'
  '*.wasm'
)

need_tools=(brotli gzip zstd)
missing=()
for t in "${need_tools[@]}"; do
  if ! command -v "$t" >/dev/null 2>&1; then
    missing+=("$t")
  fi
done
if ((${#missing[@]})); then
  echo "Missing required tools: ${missing[*]} (apt install brotli zstd)" >&2
  exit 1
fi

brotli_cmd() { brotli -f -q 11 --keep "$1"; }
gzip_cmd()   { gzip   -f -9 -k -n "$1"; }
zstd_cmd()   { zstd   -f -19 -k "$1"; }

newer() { [[ ! -f "$2" || "$1" -nt "$2" ]]; }

compress_file() {
  local f="$1"
  newer "$f" "$f.br" && brotli_cmd "$f"
  newer "$f" "$f.gz" && gzip_cmd "$f"
  newer "$f" "$f.zst" && zstd_cmd "$f"
}

export -f brotli_cmd gzip_cmd zstd_cmd newer compress_file

if command -v nproc >/dev/null 2>&1; then
  NPROC="$(nproc)"
else
  NPROC=4
fi
if ((NPROC < 1)); then
  NPROC=1
fi

export NPROC

find_cmd=(find "$DIR" -type f '(' -name "${GLOBS[0]}" )
for pattern in "${GLOBS[@]:1}"; do
  find_cmd+=(-o -name "$pattern")
done
find_cmd+=(')' ! -name '*.br' ! -name '*.gz' ! -name '*.zst')

if ! "${find_cmd[@]}" -print -quit >/dev/null; then
  echo "No matching assets found for compression in: $DIR"
  exit 0
fi

"${find_cmd[@]}" -print0 | xargs -0 -P "$NPROC" -n 1 bash -c 'compress_file "$1"' _

echo "Precompression done in: $DIR"
