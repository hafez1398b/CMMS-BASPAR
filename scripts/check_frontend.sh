#!/usr/bin/env bash
# Frontend syntax guard — every ES module must parse as ESM.
# (A single broken file blanks the whole SPA, so this runs in CI.)
set -uo pipefail
cd "$(dirname "$0")/.."
fail=0
tmp=$(mktemp /tmp/check_XXXX.mjs)
for f in $(find frontend/assets/js -name '*.js'); do
  cp "$f" "$tmp"
  if ! node --check "$tmp" 2>/dev/null; then
    echo "SYNTAX FAIL: $f"
    node --check "$tmp" || true
    fail=1
  fi
done
rm -f "$tmp"
if [ "$fail" -eq 0 ]; then echo "FRONTEND SYNTAX OK"; fi
exit $fail
