.PHONY: check

# Single entry point an agent or a person can run before committing/opening
# a PR: prints one line on success, only the failing output on error, and
# always keeps the full log at .check.log (gitignored) to grep afterward.
#
# Runs `prek run --all-files`, a full-tree `gitleaks dir .`, a plain
# no-fix `ruff check .`, and pytest -- not prek alone, for two reasons:
#
# - The gitleaks pre-commit hook is `gitleaks git --staged`-only (see
#   .pre-commit-config.yaml), which is a no-op on a clean tree with
#   nothing staged -- exactly the state this target runs in. Without
#   the explicit `gitleaks dir .` step, a secret already committed
#   earlier would pass this target silently.
# - `prek run --all-files` only sees git-TRACKED files (it lists them via
#   git, same as pre-commit) -- an untracked, not-yet-`git add`-ed file is
#   invisible to it entirely, not merely silently autofixed. Confirmed by
#   testing: a new file with a real lint error (F841) is NOT caught by the
#   prek step alone. `ruff check .`/`ruff format --check .` walk the
#   filesystem directly (respecting .gitignore, not git's index), so they
#   see it regardless of tracked state. Both run without --fix so a file
#   this target merely inspects is never mutated by it.
check:
	@prek run --all-files > .check.log 2>&1 || { tail -30 .check.log; exit 1; }
	@gitleaks dir . --no-banner >> .check.log 2>&1 || { tail -30 .check.log; exit 1; }
	@.venv/bin/ruff check . >> .check.log 2>&1 || { tail -30 .check.log; exit 1; }
	@.venv/bin/ruff format --check . >> .check.log 2>&1 || { tail -30 .check.log; exit 1; }
	@.venv/bin/python -m pytest --tb=line >> .check.log 2>&1 || { tail -30 .check.log; exit 1; }
	@tail -1 .check.log
