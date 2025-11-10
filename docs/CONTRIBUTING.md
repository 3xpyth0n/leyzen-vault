# Contributing to Leyzen Vault

We are excited to collaborate with the community on Leyzen Vault, a modular moving-target defense orchestrator. This document
explains how to propose changes and what to expect from the review process. By contributing
you agree to follow the [Code of Conduct](docs/CODE_OF_CONDUCT.md).

## Workflow Overview

1. **Fork** `leyzen-vault` on GitHub and clone your fork locally.
2. **Create a topic branch** from `main` that describes your change, for example `feature/vault-enhancement`.
3. **Commit regularly** following the message guidance below.
4. **Verify everything** through the project CLI (`./leyzenctl`) before you open a pull request.
5. **Open a pull request** from your forked branch back to `main` and request review.

Keeping each branch scoped to a single improvement helps reviewers merge your work quickly.

## Local Environment

- Follow the installation prerequisites listed in the [README](README.md).
- Copy `env.template` to `.env` and supply the secrets requested in the file.
- Use `./leyzenctl` for all lifecycle commands (`build`, `start`, `restart`, `stop`, etc.). Direct Docker commands or
- Install and use pre-commit hooks for automatic code quality checks (see [Pre-commit Hooks](#pre-commit-hooks) below).
  manual invocations of the Compose builder are unsupported and may leave the generated artifacts inconsistent.
- Review the [Quickstart](https://github.com/3xpyth0n/leyzen-vault/wiki/Quickstart) for day-to-day usage tips and the
  [Architecture](https://github.com/3xpyth0n/leyzen-vault/wiki/Architecture) guide for implementation details.

## Pre-commit Hooks

Leyzen Vault uses [pre-commit](https://pre-commit.com/) to automatically run code quality checks before each commit. This ensures consistent code style and catches common issues early.

### Installation

Install pre-commit and enable the hooks:

```bash
pip install pre-commit
pre-commit install
```

The hooks will now run automatically on every `git commit`. You can also run them manually on all files:

```bash
pre-commit run --all-files
```

### What gets checked

The pre-commit configuration (`.pre-commit-config.yaml`) includes:

- **Ruff**: Python linting and formatting (runs on `src/` and `infra/` Python files)
- **Shellcheck**: Shell script linting (runs on `*.sh` and `*.bash` files)
- **YAML lint**: Validates YAML files for syntax errors
- **Trailing whitespace**: Removes trailing whitespace (excludes Markdown files)
- **End of file**: Ensures files end with a newline
- **Large files**: Warns if files exceed 500KB
- **Merge conflicts**: Detects merge conflict markers

If any hook fails, the commit will be blocked. Fix the issues and try committing again. Some hooks (like Ruff) can automatically fix issues—if they do, you'll need to stage the fixed files and commit again.

## Verification Expectations

Before submitting a pull request:

- Run `./leyzenctl build` to regenerate images and assets.
- Run `./leyzenctl start` (or `./leyzenctl restart` for an existing environment) to rebuild the Compose and HAProxy
  configurations and verify the stack boots without errors.
- Inspect the regenerated `docker-generated.yml` and `haproxy/haproxy.cfg` when your change impacts
  routing or environment handling.
- Update relevant pages in the [GitHub Wiki](https://github.com/3xpyth0n/leyzen-vault/wiki) when behavior or workflows change.

## Commit Message Convention

We follow a lightweight format to keep history readable:

- A short, English subject line (<= 72 characters).
- A body of up to four lines that answers:
  1. **Context** — why the change is needed.
  2. **Change** — what was done.
  3. **Verification** — which `./leyzenctl` actions or other checks were run.
  4. **Impact** — anything reviewers or operators should watch for.

Example:

```
Refine Vault bootstrap logging

Describe Vault initialization failures in the CLI output.
Ran ./leyzenctl build and ./leyzenctl start locally.
Expect clearer troubleshooting with no config changes.
```

## Pull Request Checklist

When you open a pull request, please:

- Confirm all commits follow the message convention above.
- Reference related issues or discussions so maintainers can track context.
- Include screenshots or recordings for user-facing changes to the orchestrator dashboard.
- Note any documentation you updated or intentionally left unchanged.
- Mention if the change requires coordination with downstream deployments.

Reviewers rely on this information to prioritize and merge contributions.

## Reporting Issues

Search the [issue tracker](https://github.com/3xpyth0n/leyzen-vault/issues) before filing a new report. If no existing issue
matches, open a new one using the appropriate template and include:

- Clear reproduction steps, including the `./leyzenctl` commands you executed.
- Expected versus actual results.
- Relevant logs, screenshots, or generated artifacts.

Security issues should be reported privately following the [Security Policy](docs/SECURITY.md).

## Additional Resources

- [Developer Guide](https://github.com/3xpyth0n/leyzen-vault/wiki/Developer-Guide) — contributing to Leyzen Vault.
- [Maintainer guidance](https://github.com/3xpyth0n/leyzen-vault/wiki/CI-CD) — triage, reviews, and releases.
- [Architecture](https://github.com/3xpyth0n/leyzen-vault/wiki/Architecture) — runtime internals.
- [Quickstart](https://github.com/3xpyth0n/leyzen-vault/wiki/Quickstart) — operating the stack with `leyzenctl`.
