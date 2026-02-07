# Prerequisites & Setup

## Proxy (Required)

> **Warning:** A residential proxy with sticky sessions is required. Without a proxy, requests to Google will silently fail -- you will get no error message, just zero results.

Google blocks datacenter IP addresses from accessing Maps data. You need a residential or mobile proxy that:

- Provides **sticky sessions** with at least **30 minutes** of session lifetime
- Routes through **residential IPs** (not datacenter)
- Supports **HTTP proxy protocol**

Your proxy URL should follow this format:

```
http://username:password@host:port
```

Some providers use session parameters in the password field:

```
http://user:pass_country-us_session-abc123_lifetime-30m@proxy.example.com:8080
```

There are three ways to configure the proxy, covered in detail in [Configuration](configuration.md):

1. **Constructor argument** (recommended for library usage):
   ```python
   GMapsExtractor(proxy="http://user:pass@host:port")
   ```

2. **Environment variables** (recommended for CLI usage):
   ```bash
   export GMAPS_PROXY_HOST="host:port"
   export GMAPS_PROXY_USER="username"
   export GMAPS_PROXY_PASS="password"
   ```

3. **Config file** (repo-clone users only):
   ```bash
   cp gmaps_extractor/config.example.py gmaps_extractor/config.py
   # Edit config.py with your proxy credentials
   ```

## Cookies

Google cookies are required for fetching reviews and place details. The library handles cookies automatically:

1. It visits `google.com`, `consent.google.com`, and `maps.google.com` through your proxy
2. It captures the `NID`, `AEC`, and `SOCS` cookies from those visits
3. Cookies are cached for 1 hour and auto-refreshed when expired

You do not need to configure cookies manually. If automatic fetching fails (rare), you can provide them via the `GMAPS_COOKIES` environment variable or the `cookies` constructor parameter. See [Configuration](configuration.md) for details.

## Next Steps

Once your proxy is ready, continue to the [Quick Start](quick-start.md).
