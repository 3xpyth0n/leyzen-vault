# Leyzenctl

`leyzenctl` is a standalone Go command-line application that provides lifecycle management for the Leyzen Vault Docker stack alongside environment configuration helpers.

## Building

```bash
./install.sh
```

> **Tip:** run `go mod tidy` after pulling updates to ensure dependencies are present.

## Usage

```bash
./leyzenctl --help
```

### Stack management

```bash
./leyzenctl start      # docker compose up -d --remove-orphans
./leyzenctl stop       # docker compose down
./leyzenctl restart    # stop then start
./leyzenctl build      # docker compose up -d --build
./leyzenctl status     # docker ps summary with colorized health info
```

### Environment configuration

```bash
./leyzenctl config list
./leyzenctl config set VAULT_REPLICAS 3
./leyzenctl config wizard
```

- `config list` renders the active `.env` values in a colorized table.
- `config set` validates the key/value pair before persisting to `.env`.
- `config wizard` launches an interactive survey that walks through the key Vault settings.
