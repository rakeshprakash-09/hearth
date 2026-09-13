"""Launch uvicorn per .env config: http (default) or https (uvicorn terminates
TLS itself; Caddy not required). HTTPS without cert/key files fails loudly.

Run with: python -m app.run
"""

import sys

import uvicorn

from . import config


def main() -> None:
    if config.SERVE_MODE not in ("http", "https"):
        sys.exit(f"HEARTH_SERVE must be 'http' or 'https', got {config.SERVE_MODE!r}")

    kwargs = {"host": config.BIND_HOST, "port": config.PORT}
    if config.SERVE_MODE == "https":
        missing = [p for p in (config.TLS_CERT, config.TLS_KEY) if not p]
        if missing:
            sys.exit(
                "HEARTH_SERVE=https requires HEARTH_TLS_CERT and HEARTH_TLS_KEY "
                f"in .env (missing: {', '.join(missing)})"
            )
        for p in (config.TLS_CERT, config.TLS_KEY):
            import os
            if not os.path.isfile(p):
                sys.exit(f"TLS file not found: {p}")
        kwargs.update(ssl_certfile=config.TLS_CERT, ssl_keyfile=config.TLS_KEY)

    print(f"Hearth serving {config.SERVE_MODE.upper()} on {config.BIND_HOST}:{config.PORT}")
    uvicorn.run("app.main:app", **kwargs)


if __name__ == "__main__":
    main()
