# Leyzen Vault

**Version 2.4.0**

[![CI](https://github.com/3xpyth0n/leyzen-vault/actions/workflows/ci.yml/badge.svg)](https://github.com/3xpyth0n/leyzen-vault/actions/workflows/ci.yml)
[![License: BSL 1.1](https://img.shields.io/badge/License-BSL--1.1-0A7AA6)](https://github.com/3xpyth0n/leyzen-vault/blob/main/LICENSE)
[![Contributions welcome](https://img.shields.io/badge/contributions-welcome-brightgreen.svg)](https://github.com/3xpyth0n/leyzen-vault/issues)

Leyzen Vault is a self-hosted file storage system built on a core idea: you shouldn't trust a backend system forever.

Our focus isn't just on stopping intruders. We also look at how to limit how long a breach can last and lessen its impact if the backend is compromised.

## What It's About

Leyzen Vault brings together:

- file encryption on the client side
- regular rebuilding of backend containers (learn about [Moving Target Defense](https://www.dhs.gov/archive/science-and-technology/csd-mtd))
- clear boundaries of trust between different parts

The aim here isn't to get rid of all risk. Instead, it's about restricting what a compromised backend can keep or get to over time. (_Maybe yes, try to get rid of all risk finally..._)

## Getting Started

```bash
git clone https://github.com/3xpyth0n/leyzen-vault.git
cd leyzen-vault
cp env.template .env
./install.sh
./leyzenctl start
```

You can do the first setup at /setup.

## Documentation

For complete documentation, see:
[docs.leyzen.com](https://docs.leyzen.com)

## Contributing

Contributions are welcome, either by requesting features, including bug reports, or documentation improvements. And of course, code contributions are welcome!

## Activity

![Alt](https://repobeats.axiom.co/api/embed/dacac14edc54fdcb66274584d1ba09544c99d929.svg "Repobeats analytics image")

## License

It's under the Business Source License 1.1 (BSL 1.1).
Check the [`LICENSE`](LICENSE) file for more info.
