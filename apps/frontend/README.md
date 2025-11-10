# Frontend Build Notes

The build pipeline runs `npm run build`, which triggers `scripts/precompress.sh` as a postbuild step to generate Brotli, gzip, and zstd variants of static assets.

## Prerequisites

This step requires the `brotli`, `gzip`, and `zstd` command line tools to be installed on the build host (for example, `apt install brotli zstd`).
