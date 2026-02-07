# Configuration

Configuration is resolved in this order (highest priority first):

1. **Constructor arguments** passed to `GMapsExtractor()`
2. **Environment variables**
3. **config.py defaults** (repo-clone users only)

## Constructor Arguments

The most direct way to configure when using the library. See [Python Library API](python-api.md) for the full parameter table.

```python
from gmaps_extractor import GMapsExtractor

extractor = GMapsExtractor(
    proxy="http://user:pass@host:port",
    workers=30,
    server_port=9000,
    verbose=False,
)
```

## Environment Variables

Works for both library and CLI usage.

| Variable | Description | Example |
|----------|-------------|---------|
| `GMAPS_PROXY_HOST` | Proxy hostname and port | `proxy.example.com:8080` |
| `GMAPS_PROXY_USER` | Proxy username | `myuser` |
| `GMAPS_PROXY_PASS` | Proxy password (may include session params) | `mypass_country-us_session-abc_lifetime-30m` |
| `GMAPS_COOKIES` | JSON string of Google cookies | `{"NID":"...","SOCS":"..."}` |

All three proxy variables (`HOST`, `USER`, `PASS`) must be set for the proxy to be assembled. The resulting URL is `http://{USER}:{PASS}@{HOST}`.

**Setting environment variables:**

```bash
# Linux/macOS
export GMAPS_PROXY_HOST="proxy.example.com:8080"
export GMAPS_PROXY_USER="myuser"
export GMAPS_PROXY_PASS="mypass"

# Windows (cmd)
set GMAPS_PROXY_HOST=proxy.example.com:8080
set GMAPS_PROXY_USER=myuser
set GMAPS_PROXY_PASS=mypass

# Windows (PowerShell)
$env:GMAPS_PROXY_HOST = "proxy.example.com:8080"
$env:GMAPS_PROXY_USER = "myuser"
$env:GMAPS_PROXY_PASS = "mypass"
```

## Config File (Repo-Clone Users)

If you cloned the repository, you can use a config file:

```bash
cp gmaps_extractor/config.example.py gmaps_extractor/config.py
```

Edit `config.py` and fill in your proxy credentials. This file is gitignored.

> **Note:** pip-installed users do not have `config.py`. The package falls back to `_config_defaults.py` which has empty placeholders. Use constructor arguments or environment variables instead.

## Proxy URL Format

A single `proxy` string passed to the constructor:

```
http://username:password@hostname:port
```

Examples:

```python
# Simple proxy
GMapsExtractor(proxy="http://user:pass@proxy.example.com:8080")

# Proxy with session parameters in password
GMapsExtractor(proxy="http://user:pass_country-us_session-xyz_lifetime-30m@proxy.example.com:8080")
```

## Cookie Configuration

Cookies are auto-managed and rarely need manual configuration. The system:

1. Checks the `GMAPS_COOKIES` environment variable
2. Uses cached cookies if still valid (1-hour TTL)
3. Auto-fetches fresh cookies from Google through your proxy

To override manually:

```python
GMapsExtractor(cookies={"NID": "...", "SOCS": "...", "__Secure-BUCKET": "CGA"})
```

Or via environment variable:

```bash
export GMAPS_COOKIES='{"NID":"abc123","SOCS":"def456"}'
```
