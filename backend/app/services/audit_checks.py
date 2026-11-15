"""
Non-destructive security checks for web targets.

Rules (spec section 3.3 / rule 7-8):
- ONLY plain HTTP GET requests; nothing invasive, nothing destructive.
- Every finding carries real technical evidence.
- If a check cannot run (network error), the result is recorded as a
  check error — never guessed.
"""
import json
import ssl
import socket
import urllib.error
import urllib.request
from datetime import datetime, timezone


REQUEST_TIMEOUT = 10


def http_get(url: str, timeout: int = REQUEST_TIMEOUT) -> dict:
    """Plain GET. Returns {status, headers, body, error}."""
    result = {"url": url, "status": None, "headers": {}, "body": "", "error": None}

    try:
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "SentinelAI-Auditor/0.1 (authorized audit)"},
            method="GET",
        )

        with urllib.request.urlopen(request, timeout=timeout) as response:
            result["status"] = response.status
            result["headers"] = {
                key.lower(): value
                for key, value in response.headers.items()
            }
            result["body"] = response.read(20000).decode(
                "utf-8", errors="replace"
            )

    except urllib.error.HTTPError as error:
        # HTTP error responses are still valid evidence
        result["status"] = error.code
        result["headers"] = {
            key.lower(): value for key, value in error.headers.items()
        }

    except (urllib.error.URLError, OSError, ValueError) as error:
        result["error"] = str(error)

    return result


def tls_info(host: str, port: int = 443, timeout: int = REQUEST_TIMEOUT) -> dict:
    """Inspect the TLS certificate. Returns evidence dict."""
    info: dict = {"host": host, "port": port}

    try:
        context = ssl.create_default_context()

        with socket.create_connection((host, port), timeout=timeout) as sock:
            with context.wrap_socket(sock, server_hostname=host) as tls:
                cert = tls.getpeercert()

        not_after = cert.get("notAfter")

        if not_after:
            expires = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z").replace(
                tzinfo=timezone.utc
            )
            days_left = (expires - datetime.now(timezone.utc)).days
            info["not_after"] = not_after
            info["days_left"] = days_left

        issuer = cert.get("issuer")
        info["issuer"] = " ".join(
            part for rdn in (issuer or []) for part in rdn
        ) or None

    except ssl.SSLCertVerificationError as error:
        info["error"] = f"certificate verification failed: {error.verify_message}"
        info["invalid_cert"] = True

    except (socket.timeout, OSError) as error:
        info["error"] = f"TLS connection failed: {error}"

    return info


def determine_web_url(
    host: str, timeout: int = 3
) -> str | None:
    """Probe an IP/hostname for a web service.

    https preferred (even with invalid certs — that is itself a
    finding); falls back to http. Returns None when neither is
    reachable — the asset gets NO audit URL, and we honestly say so.
    Module-level so tests can stub it.
    """
    # https first
    try:
        with socket.create_connection((host, 443), timeout=timeout):
            return f"https://{host}"
    except OSError:
        pass

    try:
        with socket.create_connection((host, 80), timeout=timeout):
            return f"http://{host}"
    except OSError:
        return None
