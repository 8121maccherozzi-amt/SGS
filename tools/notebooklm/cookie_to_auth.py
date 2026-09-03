#!/usr/bin/env python3
"""Converte una riga di header HTTP 'Cookie:' nel formato storage_state JSON
atteso da notebooklm-py (variabile NOTEBOOKLM_AUTH_JSON).

La riga si ottiene dal browser: DevTools (F12) -> Network -> ricarica la
pagina -> clic sulla prima richiesta a notebooklm.google.com -> Headers ->
Request Headers -> valore di 'cookie:'.

Uso:
    python3 cookie_to_auth.py --input cookie.txt --email tu@example.com > auth.json

ATTENZIONE: il file prodotto contiene credenziali equivalenti all'accesso
all'intero account Google. Non committarlo e non condividerlo.
"""

from __future__ import annotations

import argparse
import json
import sys

# Cookie host-scoped su notebooklm.google.com; tutto il resto sta su .google.com
HOST_SCOPED = {"OSID", "__Secure-OSID", "__Host-GAPS"}

TIER1 = {"SID", "__Secure-1PSIDTS"}
TIER2_ANY = {"OSID"}
TIER2_SET = {"APISID", "SAPISID", "LSID"}


def parse_cookie_header(raw: str) -> list[dict]:
    raw = raw.strip()
    if raw.lower().startswith("cookie:"):
        raw = raw.split(":", 1)[1].strip()

    cookies = []
    seen = set()
    for part in raw.split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        name, value = part.split("=", 1)
        name, value = name.strip(), value.strip()
        if not name or name in seen:
            continue
        seen.add(name)
        domain = "notebooklm.google.com" if name in HOST_SCOPED else ".google.com"
        cookies.append(
            {
                "name": name,
                "value": value,
                "domain": domain,
                "path": "/",
                "httpOnly": True,
                "secure": True,
                "sameSite": "None" if name.startswith("__Secure-3P") else "Lax",
            }
        )
    return cookies


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", "-i", required=True, help="file contenente la riga Cookie:")
    ap.add_argument("--email", "-e", default="", help="email dell'account Google")
    ap.add_argument("--authuser", type=int, default=0)
    args = ap.parse_args()

    with open(args.input, encoding="utf-8") as fh:
        cookies = parse_cookie_header(fh.read())

    names = {c["name"] for c in cookies}
    missing_t1 = TIER1 - names
    if missing_t1:
        print(f"ERRORE: cookie obbligatori mancanti: {sorted(missing_t1)}", file=sys.stderr)
        sys.exit(1)
    if not (names & TIER2_ANY) and not TIER2_SET.issubset(names):
        print(
            "ATTENZIONE: manca il binding secondario (OSID oppure APISID+SAPISID+LSID); "
            "la sessione potrebbe essere rifiutata.",
            file=sys.stderr,
        )

    payload = {
        "cookies": cookies,
        "origins": [],
        "notebooklm": {
            "version": 1,
            "account": {"authuser": args.authuser, "email": args.email},
        },
    }
    print(json.dumps(payload, ensure_ascii=False))
    print(f"OK: {len(cookies)} cookie convertiti.", file=sys.stderr)


if __name__ == "__main__":
    main()
