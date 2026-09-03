#!/usr/bin/env python3
"""Normalizza i cookie di sessione nel formato storage_state JSON atteso da
notebooklm-py (variabile NOTEBOOKLM_AUTH_JSON).

Accetta tre formati di input, riconosciuti automaticamente:

1. Riga di header HTTP `Cookie:` — DevTools (F12) -> Network -> ricarica la
   pagina -> clic sulla prima richiesta a notebooklm.google.com -> Headers ->
   Request Headers -> valore di 'cookie:'.
2. Array JSON esportato da un'estensione browser (EditThisCookie, Cookie
   Editor e simili): [{"name": ..., "value": ..., "domain": ...}, ...].
3. storage_state JSON gia' pronto: {"cookies": [...], "origins": [...]}.

L'input si legge da --input, oppure dalla variabile d'ambiente
NOTEBOOKLM_AUTH_JSON, oppure da stdin.

Uso:
    python3 cookie_to_auth.py --input cookie.txt --email tu@example.com > auth.json
    python3 cookie_to_auth.py --from-env > auth.json

ATTENZIONE: il file prodotto contiene credenziali equivalenti all'accesso
all'intero account Google. Non committarlo e non condividerlo.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

# Cookie host-scoped su notebooklm.google.com; tutto il resto sta su .google.com
HOST_SCOPED = {"OSID", "__Secure-OSID", "__Host-GAPS"}

# Domini legacy/alternativi da ricondurre all'host effettivo dell'API
DOMAIN_ALIASES = {
    "notebook.google.com": "notebooklm.google.com",
    ".notebooklm.google.com": "notebooklm.google.com",
}

TIER1 = {"SID", "__Secure-1PSIDTS"}
TIER2_ANY = {"OSID"}
TIER2_SET = {"APISID", "SAPISID", "LSID"}

# Cookie di sessione Google privi del flag Secure: sono quelli che le
# estensioni con filtro "solo secure" e le letture parziali di Chrome 127+
# (App-Bound Encryption) tendono a perdere silenziosamente.
NON_SECURE_AUTH = {"SID", "HSID", "APISID", "LSID"}

VALID_SAMESITE = {"Lax", "Strict", "None"}

ENV_VAR = "NOTEBOOKLM_AUTH_JSON"


def default_domain(name: str) -> str:
    return "notebooklm.google.com" if name in HOST_SCOPED else ".google.com"


def normalize_domain(name: str, domain: str | None) -> str:
    if not domain:
        return default_domain(name)
    return DOMAIN_ALIASES.get(domain, domain)


def make_cookie(name: str, value: str, domain: str | None = None, **extra) -> dict:
    same_site = extra.get("sameSite")
    if same_site not in VALID_SAMESITE:
        same_site = "None" if name.startswith("__Secure-3P") else "Lax"
    return {
        "name": name,
        "value": value,
        "domain": normalize_domain(name, domain),
        "path": extra.get("path") or "/",
        "httpOnly": bool(extra.get("httpOnly", True)),
        "secure": bool(extra.get("secure", True)),
        "sameSite": same_site,
    }


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
        cookies.append(make_cookie(name, value))
    return cookies


def parse_cookie_entries(entries: list) -> list[dict]:
    """Array JSON da estensione browser, o la lista 'cookies' di uno storage_state."""
    cookies = []
    seen = set()
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        name = (entry.get("name") or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        cookies.append(
            make_cookie(
                name,
                entry.get("value", ""),
                entry.get("domain"),
                path=entry.get("path"),
                httpOnly=entry.get("httpOnly", True),
                secure=entry.get("secure", True),
                sameSite=entry.get("sameSite"),
            )
        )
    return cookies


def parse_any(raw: str) -> tuple[list[dict], str]:
    """Riconosce il formato dell'input e restituisce (cookies, nome_formato)."""
    stripped = raw.strip()
    if stripped[:1] in ("[", "{"):
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError as exc:
            print(f"ERRORE: input JSON non valido: {exc}", file=sys.stderr)
            sys.exit(1)
        if isinstance(payload, list):
            return parse_cookie_entries(payload), "array JSON (export estensione)"
        if isinstance(payload, dict):
            entries = payload.get("cookies")
            if isinstance(entries, list):
                return parse_cookie_entries(entries), "storage_state JSON"
            print(
                "ERRORE: oggetto JSON senza campo 'cookies'.",
                file=sys.stderr,
            )
            sys.exit(1)
        print("ERRORE: JSON di tipo inatteso.", file=sys.stderr)
        sys.exit(1)
    return parse_cookie_header(stripped), "riga header Cookie:"


def read_input(path: str | None, from_env: bool) -> tuple[str, str]:
    """Restituisce (contenuto, origine)."""
    if path:
        with open(path, encoding="utf-8") as fh:
            return fh.read(), f"file {path}"
    env_value = os.environ.get(ENV_VAR)
    if from_env or (env_value and sys.stdin.isatty()):
        if not env_value:
            print(f"ERRORE: variabile {ENV_VAR} non impostata.", file=sys.stderr)
            sys.exit(1)
        return env_value, f"variabile {ENV_VAR}"
    return sys.stdin.read(), "stdin"


def validate(names: set[str]) -> None:
    missing_t1 = TIER1 - names
    if missing_t1:
        print(
            f"ERRORE: cookie obbligatori mancanti: {sorted(missing_t1)}",
            file=sys.stderr,
        )
        missing_non_secure = NON_SECURE_AUTH - names
        if missing_non_secure == NON_SECURE_AUTH:
            print(
                "DIAGNOSI: mancano tutti i cookie di sessione privi del flag Secure "
                f"({sorted(NON_SECURE_AUTH)}). Tipico di un export filtrato "
                "'solo cookie secure' o di una lettura parziale del profilo Chrome "
                "127+ (App-Bound Encryption). Rigenera il payload copiando la riga "
                "'cookie:' completa dagli header di richiesta in DevTools -> Network.",
                file=sys.stderr,
            )
        sys.exit(1)
    if not (names & TIER2_ANY) and not TIER2_SET.issubset(names):
        print(
            "ATTENZIONE: manca il binding secondario (OSID oppure APISID+SAPISID+LSID); "
            "la sessione potrebbe essere rifiutata.",
            file=sys.stderr,
        )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--input",
        "-i",
        help=(
            "file con la riga Cookie:, un array JSON di cookie o uno storage_state. "
            f"Senza questa opzione si usa la variabile {ENV_VAR} oppure stdin."
        ),
    )
    ap.add_argument(
        "--from-env",
        action="store_true",
        help=f"forza la lettura dalla variabile d'ambiente {ENV_VAR}",
    )
    ap.add_argument("--email", "-e", default="", help="email dell'account Google")
    ap.add_argument("--authuser", type=int, default=0)
    args = ap.parse_args()

    raw, source = read_input(args.input, args.from_env)
    if not raw.strip():
        print(f"ERRORE: input vuoto ({source}).", file=sys.stderr)
        sys.exit(1)

    cookies, fmt = parse_any(raw)
    if not cookies:
        print(f"ERRORE: nessun cookie riconosciuto ({source}, {fmt}).", file=sys.stderr)
        sys.exit(1)

    validate({c["name"] for c in cookies})

    payload = {
        "cookies": cookies,
        "origins": [],
        "notebooklm": {
            "version": 1,
            "account": {"authuser": args.authuser, "email": args.email},
        },
    }
    print(json.dumps(payload, ensure_ascii=False))
    print(f"OK: {len(cookies)} cookie normalizzati da {source} ({fmt}).", file=sys.stderr)


if __name__ == "__main__":
    main()
