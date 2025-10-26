# Vulnerability Management Process

This service keeps its Python dependencies pinned and reviewed on a fixed cadence to
avoid silently picking up vulnerabilities.

## Dependency pinning workflow

1. Edit `requirements.in` when you need to add or remove top-level dependencies.
2. Regenerate `requirements.txt` with fully pinned versions:
   ```bash
   cd orchestrator
   pip-compile requirements.in --output-file requirements.txt
   pip freeze | grep -E '^(Flask|Flask-WTF|requests|pytz)=='
   ```
   The `pip freeze` command double-checks that the installed versions match what
   is written to the lock file.
3. Commit both files and rebuild the Docker image.

## Regular CVE reviews

Perform a dependency vulnerability review at least once per month and before
any release:

1. Update the lock files (`pip-compile`) to pick up patched versions.
2. Run `pip-audit` against the current environment to identify known CVEs:
   ```bash
   pipx run pip-audit
   ```
3. Track findings in the issue tracker, documenting mitigation steps or
   acceptance of risk for each CVE.
4. For critical or high-severity issues, release patched containers within 24
   hours.

Record the review date and outcome in the project changelog to maintain an audit trail.
