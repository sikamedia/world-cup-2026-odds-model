#!/usr/bin/env bash
# Run the active test suite: every root test_*.py plus the skill regression test.
# Each test is a standalone script using module-level asserts; non-zero = fail.
set -u
cd "$(dirname "$0")"

fail=0
for t in test_*.py skill/test_regression.py; do
  [ -f "$t" ] || continue
  if python3 "$t" >/dev/null 2>&1; then
    printf 'PASS  %s\n' "$t"
  else
    printf 'FAIL  %s\n' "$t"
    python3 "$t" 2>&1 | tail -6 | sed 's/^/      /'
    fail=1
  fi
done

echo
[ "$fail" -eq 0 ] && echo "All tests passed." || echo "Some tests FAILED."
exit "$fail"
