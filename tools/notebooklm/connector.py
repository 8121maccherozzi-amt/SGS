#!/usr/bin/env python3
"""Connettore non ufficiale verso NotebookLM (Gemini Notebook).

Elenca i notebook dell'account autenticato e ne esporta fonti e note in
locale come file di testo. Si appoggia alla libreria open source
`notebooklm-py`, che dialoga con l'API interna (non pubblica) di
NotebookLM tramite i cookie di sessione del browser.

Autenticazione: richiede la variabile d'ambiente NOTEBOOKLM_AUTH_JSON,
contenente il payload JSON dei cookie (vedi README.md in questa cartella
per il formato e come generarla). Lo script non legge né scrive mai il
cookie su file: si affida esclusivamente alla libreria e alla variabile
d'ambiente già presente nel processo.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path


def _safe_slug(text: str, fallback: str) -> str:
    text = (text or "").strip()
    slug = "".join(c if c.isalnum() or c in "-_" else "_" for c in text)
    slug = slug.strip("_")
    return (slug or fallback)[:80]


async def export_notebooks(output_dir: Path, notebook_id: str | None) -> int:
    from notebooklm import NotebookLMClient

    async with NotebookLMClient.from_storage() as client:
        notebooks = await client.notebooks.list()

        if notebook_id:
            notebooks = [nb for nb in notebooks if nb.id == notebook_id]
            if not notebooks:
                print(f"Notebook '{notebook_id}' non trovato.", file=sys.stderr)
                return 1

        if not notebooks:
            print("Nessun notebook trovato per questo account.")
            return 0

        index = []
        for nb in notebooks:
            nb_dir = output_dir / _safe_slug(nb.title, nb.id)
            nb_dir.mkdir(parents=True, exist_ok=True)
            print(f"[notebook] {nb.title} ({nb.id}) - {nb.sources_count} fonti")

            sources_meta = []
            for src in await client.sources.list(nb.id):
                try:
                    fulltext = await client.sources.get_fulltext(nb.id, src.id)
                except Exception as exc:  # fonte non testuale / non pronta / errore RPC
                    print(f"  ! fonte '{src.title}' saltata: {exc}", file=sys.stderr)
                    continue
                fname = _safe_slug(src.title, src.id) + ".txt"
                (nb_dir / fname).write_text(fulltext.content, encoding="utf-8")
                sources_meta.append({"id": src.id, "title": src.title, "file": fname})
                print(f"  - fonte: {src.title} -> {fname}")

            notes_meta = []
            for note in await client.notes.list(nb.id):
                full_note = await client.notes.get(nb.id, note.id)
                fname = _safe_slug(note.title or note.id, note.id) + ".md"
                (nb_dir / fname).write_text(full_note.content or "", encoding="utf-8")
                notes_meta.append({"id": note.id, "title": note.title, "file": fname})
                print(f"  - nota: {note.title} -> {fname}")

            (nb_dir / "_metadata.json").write_text(
                json.dumps(
                    {
                        "id": nb.id,
                        "title": nb.title,
                        "sources": sources_meta,
                        "notes": notes_meta,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            index.append(
                {"id": nb.id, "title": nb.title, "dir": nb_dir.relative_to(output_dir).as_posix()}
            )

        (output_dir / "index.json").write_text(
            json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"\nCompletato: {len(index)} notebook esportati in {output_dir}")
        return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Elenca e scarica (fonti/note) i notebook da NotebookLM."
    )
    parser.add_argument(
        "--output", "-o", default="notebooklm_export", help="Cartella di output (default: ./notebooklm_export)"
    )
    parser.add_argument(
        "--notebook", "-n", default=None, help="Esporta solo il notebook con questo ID"
    )
    args = parser.parse_args()

    if not os.environ.get("NOTEBOOKLM_AUTH_JSON"):
        print(
            "NOTEBOOKLM_AUTH_JSON non impostata: serve il payload di autenticazione "
            "(cookie) esportato dal browser. Vedi tools/notebooklm/README.md.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    raise SystemExit(asyncio.run(export_notebooks(output_dir, args.notebook)))


if __name__ == "__main__":
    main()
