# Contributing Guide

We welcome contributions that improve Leyzen Vault. Follow the guidelines below to help maintainers review your work quickly and effectively.

## Getting Started

1. Fork the repository and create your branch from `main`.
2. Install project prerequisites listed in the [README](README.md#prerequisites-).
3. Copy `env.template` to `.env` and provide the required secrets locally.
4. Use `./service.sh start` to launch the Docker stack when testing orchestration changes.

## Coding Standards

- Keep all documentation and comments in English.
- Follow existing code style conventions in the repository.
- Add or update tests whenever practical.
- Run available checks before submitting your changes.

## Commit and PR Guidelines

- Write descriptive commit messages that explain the “why” behind changes.
- Keep pull requests focused and scoped to a single improvement.
- Include screenshots when changing user-facing dashboards or UI flows.
- Ensure the PR description summarizes the motivation, implementation, and testing steps.

## Reporting Issues

If you encounter a bug or have a feature request:

- Search the [issue tracker](https://github.com/3xpyth0n/leyzen-vault/issues) to avoid duplicates.
- Open a new issue with clear reproduction steps, expected behavior, and logs when available.

Thank you for helping improve Leyzen Vault!
