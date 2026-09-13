#!/usr/bin/env bash
# Secret scan for `make check`: runs `gitleaks dir` over exactly the files
# git can see -- tracked files plus untracked files that are not
# gitignored -- instead of the raw working directory.
#
# A plain `gitleaks dir .` also walks gitignored local state (.env, a
# Home Assistant dev instance under config/) and reports the real
# credentials there. Those files cannot reach a commit without
# `git add -f`, and a forced add is still caught by the staged-diff
# gitleaks pre-commit hook. Reporting them on every run only trains
# people to skip past a failing gate. Pinning them in .gitleaksignore
# would be worse: they are real secrets, not false positives, and HA
# rewrites .storage often enough that the fingerprints would go stale.
#
# CI keeps `gitleaks dir .` on a fresh checkout, which has no ignored
# files, so both scans cover the same set.

set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"

scan_dir="$(mktemp -d)"
trap 'rm -rf "$scan_dir"' EXIT

# Tracked files deleted in the working tree are still listed by git;
# skip them so tar does not fail on a missing path. Symlinks are kept.
git ls-files -z --cached --others --exclude-standard |
	while IFS= read -r -d '' path; do
		if [ -e "$path" ] || [ -L "$path" ]; then
			printf '%s\0' "$path"
		fi
	done |
	tar --null -T - -cf - |
	tar -xf - -C "$scan_dir"

# An empty copy would scan nothing and pass silently.
if [ ! -f "$scan_dir/Makefile" ]; then
	echo "scan_secrets: copy of the git-visible tree is empty" >&2
	exit 1
fi

# .gitleaksignore fingerprints are relative paths, which the copy keeps.
cd "$scan_dir"
gitleaks dir . --no-banner --gitleaks-ignore-path "$root" "$@"
