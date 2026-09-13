.PHONY: setup check

# One-command contributor bootstrap for the local quality gate -- see
# scripts/setup_prek.sh for the full rationale (pinned prek, hooksPath
# detection, idempotent re-runs).
setup:
	@scripts/setup_prek.sh

# Single entry point an agent or a person can run before committing/opening
# a PR: prints one line on success, only the failing output on error, and
# always keeps the full log at .check.log (gitignored) to grep afterward.
#
# Runs `prek run --all-files`, a `gitleaks dir` scan of every git-visible
# file (scripts/scan_secrets.sh), a plain no-fix `ruff check .`, and
# pytest -- not prek alone, for two reasons:
#
# - The gitleaks pre-commit hook is `gitleaks git --staged`-only (see
#   .pre-commit-config.yaml), which is a no-op on a clean tree with
#   nothing staged -- exactly the state this target runs in. Without
#   the explicit scan step, a secret already committed earlier would
#   pass this target silently. The scan skips gitignored files, which
#   hold real local credentials but can never be committed by accident;
#   see the script for why they are not pinned in .gitleaksignore.
# - `prek run --all-files` only sees git-TRACKED files (it lists them via
#   git, same as pre-commit) -- an untracked, not-yet-`git add`-ed file is
#   invisible to it entirely, not merely silently autofixed. Confirmed by
#   testing: a new file with a real lint error (F841) is NOT caught by the
#   prek step alone. `ruff check .`/`ruff format --check .` walk the
#   filesystem directly (respecting .gitignore, not git's index), so they
#   see it regardless of tracked state. Both run without --fix so a file
#   this target merely inspects is never mutated by it.
#
# Checks that prek/gitleaks/.venv's ruff actually exist BEFORE running
# anything, with a "missing: X -- run make setup" message pointing at the
# fix -- without this, a clone that skipped `make setup` gets a raw
# "command not found" from the shell for the missing tool, buried in
# whatever else the log happened to capture first.
#
# Prefers the version-scoped prek binary `make setup` installs under
# ~/.local/state/polleninformation-prek/<version>/bin/ over a bare PATH
# lookup: an ordinary clone's `make setup` never puts that directory on
# PATH, and a stray global `prek` (a different version, or none) would
# otherwise be picked up silently, defeating the pinning. Falls back to
# PATH for machines where prek is already installed globally (e.g. via
# the maintainer's core.hooksPath dispatcher).
check:
	@prek_version=$$(grep -o 'prek==[0-9][0-9.]*' .github/workflows/test.yaml | head -n1 | cut -d= -f3); \
	persist_bin="$$HOME/.local/state/polleninformation-prek/$$prek_version/bin/prek"; \
	if [ -x "$$persist_bin" ]; then \
		prek_bin="$$persist_bin"; \
	elif command -v prek >/dev/null 2>&1; then \
		prek_bin="prek"; \
	else \
		echo "missing: prek -- run make setup"; exit 1; \
	fi; \
	command -v gitleaks >/dev/null 2>&1 || { echo "missing: gitleaks -- run make setup"; exit 1; }; \
	[ -x .venv/bin/ruff ] || { echo "missing: .venv/bin/ruff -- pip install -r requirements_dev.txt in .venv"; exit 1; }; \
	rm -f .check.log; \
	( \
		"$$prek_bin" run --all-files >> .check.log 2>&1 && \
		scripts/scan_secrets.sh >> .check.log 2>&1 && \
		.venv/bin/ruff check . >> .check.log 2>&1 && \
		.venv/bin/ruff format --check . >> .check.log 2>&1 && \
		.venv/bin/python -m pytest --tb=line >> .check.log 2>&1 \
	) && tail -1 .check.log || { tail -30 .check.log; exit 1; }
