.PHONY: check

# Single entry point an agent or a person can run before committing/opening
# a PR: prints one line on success, only the failing output on error, and
# always keeps the full log at .check.log (gitignored) to grep afterward.
#
# Runs both `prek run --all-files` and a plain, no-fix `ruff check .`
# rather than relying on prek alone: a prek --fix hook run against an
# untracked file silently fixes it and reports "Passed" (there is no index
# entry to diff against), so a brand-new, not-yet-`git add`-ed module could
# pass this target with real lint errors. The no-fix ruff check has no such
# blind spot.
check:
	@prek run --all-files > .check.log 2>&1 || { tail -30 .check.log; exit 1; }
	@.venv/bin/ruff check . >> .check.log 2>&1 || { tail -30 .check.log; exit 1; }
	@.venv/bin/python -m pytest --tb=line >> .check.log 2>&1 || { tail -30 .check.log; exit 1; }
	@tail -1 .check.log
