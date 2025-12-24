<p align="center">
  <img src="https://leyzen.com/images/vault-text-logo.png" alt="Leyzen Vault logo" height="30" />
</p>
<p align="center">
  <i>A secure alternative to traditional cloud storage, built around client-side encryption.</i>
  <br/>
  <img width="1640" style="border-radius: 12px;" alt="Vault dashboard" src="https://leyzen.com/images/vault-dashboard.png">
</p>
<p align="center">
  <a href="https://github.com/prettier/prettier">
    <img src="https://img.shields.io/badge/code_style-prettier-ff69b4.svg" alt="Prettier">
  </a>
  <a href="https://github.com/3xpyth0n/leyzen-vault/actions/workflows/ci.yml">
    <img src="https://github.com/3xpyth0n/leyzen-vault/actions/workflows/ci.yml/badge.svg" alt="CI">
  </a>
  <a href="https://github.com/3xpyth0n/leyzen-vault/issues">
    <img src="https://img.shields.io/badge/contributions-welcome-brightgreen.svg" alt="Contributions welcome">
  </a>
  <a href="https://github.com/3xpyth0n/leyzen-vault/commits/main">
  <img src="https://img.shields.io/github/last-commit/3xpyth0n/leyzen-vault" alt="Last commit">
</a>
  <a href="https://github.com/3xpyth0n/leyzen-vault/blob/main/LICENSE">
    <img src="https://img.shields.io/badge/License-BSL--1.1-0A7AA6" alt="License">
  </a>
</p>

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
