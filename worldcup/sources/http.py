"""Minimal HTTP JSON client honouring proxy/CA settings from the environment."""

from __future__ import annotations

import json
import os
import ssl
import urllib.error
import urllib.request

_USER_AGENT = "Mozilla/5.0 (compatible; WorldCupIntelligence/2.0; +https://github.com)"


class SourceError(RuntimeError):
    """Raised when a live source cannot be reached or parsed."""


def get_json(url: str, timeout: int = 25):
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    context = ssl.create_default_context()
    cafile = os.environ.get("SSL_CERT_FILE") or os.environ.get("REQUESTS_CA_BUNDLE")
    if cafile and os.path.exists(cafile):
        context.load_verify_locations(cafile)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=context) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, ssl.SSLError, ValueError) as exc:
        raise SourceError(f"GET {url} failed: {exc}") from exc
