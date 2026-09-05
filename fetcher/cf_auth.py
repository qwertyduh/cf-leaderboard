"""Build signed Codeforces API URLs for private/mashup contests.

Public contests (normal rated rounds) serve ``contest.standings`` and
``contest.status`` unauthenticated.  Mashups are different: Codeforces does
not serve them publicly, so those two methods must be called with a signed,
authenticated request carrying ``apiKey``, ``time`` and ``apiSig``.

Signing scheme (per https://codeforces.com/apiHelp):

  1. Take every query parameter *except* ``apiSig`` — including ``apiKey``
     and ``time`` — and sort them alphabetically by key.
  2. Join them as ``key1=value1&key2=value2...``.
  3. Generate a fresh random 6-character prefix ``rand`` from printable
     ASCII (codes 33–126).
  4. Build the string ``rand + "/" + method + "?" + sorted_params + "#" + secret``.
  5. SHA-512-hash that string and take the hex digest.
  6. ``apiSig = rand + digest`` — the same ``rand`` is prepended.

.. note::

    A valid signature is *necessary but not sufficient*.  The Codeforces
    account that owns ``apiKey`` must actually be a participant, coach, or
    manager of the mashup; a correctly-signed request from an unrelated
    account is still rejected with a ``FAILED`` status.  We cannot detect
    that from here — it has to be confirmed on the CF side.
"""

import hashlib
import secrets
import time
from typing import Mapping
from urllib.parse import urlencode

CF_API_BASE = "https://codeforces.com/api"

# Characters allowed in the apiSig prefix.  The CF spec permits any 6
# characters, but the prefix is round-tripped through the URL query (it is
# percent-encoded when the URL is built and decoded by CF before it re-reads
# the first 6 chars as `rand`).  Restricting to alphanumerics avoids URL
# metacharacters (`#/&=?%+`) that intermittently corrupt that round-trip and
# make CF reject an otherwise-valid signature with "Incorrect signature".
_RAND_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"


def _random_prefix(length: int = 6) -> str:
    """Return a fresh random string of printable ASCII characters."""
    return "".join(secrets.choice(_RAND_CHARS) for _ in range(length))


def compute_api_sig(
    rand: str, method: str, params: Mapping[str, object], secret: str
) -> str:
    """Compute ``apiSig`` for a signed request.

    ``params`` must already include ``apiKey`` and ``time`` (and must *not*
    include ``apiSig``).  Returns ``rand + sha512hex(...)``.
    """
    sorted_params = "&".join(
        f"{key}={value}" for key, value in sorted(params.items())
    )
    payload = f"{rand}/{method}?{sorted_params}#{secret}"
    digest = hashlib.sha512(payload.encode("utf-8")).hexdigest()
    return rand + digest


def build_signed_url(
    method: str,
    params: Mapping[str, object],
    api_key: str,
    api_secret: str,
) -> str:
    """Build a fully signed CF API URL.

    Adds ``apiKey`` and ``time`` (current unix timestamp) to *params*, sorts
    everything, signs it, and appends ``apiSig``.  Returns a complete URL
    ready for a GET request.
    """
    rand = _random_prefix()
    signed_params = dict(params)
    signed_params["apiKey"] = api_key
    signed_params["time"] = str(int(time.time()))

    # The signature is computed over the *raw* (unencoded) sorted params.
    api_sig = compute_api_sig(rand, method, signed_params, api_secret)

    # When building the URL, every value — including apiSig, whose random
    # prefix may contain '&', '=', '#', etc. — must be percent-encoded.
    query_params = dict(signed_params)
    query_params["apiSig"] = api_sig
    query = urlencode(sorted(query_params.items()))
    return f"{CF_API_BASE}/{method}?{query}"
