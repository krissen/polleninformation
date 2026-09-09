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
# - A prek --fix hook run against an untracked file silently fixes it
#   and reports "Passed" (there is no index entry to diff against), so
#   a brand-new, not-yet-`git add`-ed module could pass this target
#   with real lint errors. The no-fix ruff check has no such blind spot.
check:
	@prek run --all-files > .check.log 2>&1 || { tail -30 .check.log; exit 1; }
	@gitleaks dir . --no-banner >> .check.log 2>&1 || { tail -30 .check.log; exit 1; }
	@.venv/bin/ruff check . >> .check.log 2>&1 || { tail -30 .check.log; exit 1; }
	@.venv/bin/python -m pytest --tb=line >> .check.log 2>&1 || { tail -30 .check.log; exit 1; }
	@tail -1 .check.log
