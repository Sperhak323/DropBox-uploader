#!/usr/bin/env python3
"""
dbx_upload.py – Dropbox uploader s folder browserom pre Termux
Použitie:
    python dbx_upload.py súbor.mp4
    python dbx_upload.py foto.jpg dokument.pdf
    python dbx_upload.py /cesta/k/priecinku
    python dbx_upload.py .
    python dbx_upload.py subory/ --dest /Zaloha   # preskočí browser
"""

import sys
import os
import time
import argparse
import requests
import json

# ── Konfigurácia ──────────────────────────────────────────────────────────────
CHUNK_SIZE = 100 * 1024 * 1024   # 100 MB na chunk
THRESHOLD  = 150 * 1024 * 1024   # súbory nad 150 MB → chunked upload
# ─────────────────────────────────────────────────────────────────────────────

def load_token():
    token_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "h.txt")
    try:
        with open(token_file, "r") as f:
            token = f.read().strip()
        if not token:
            print("❌ Súbor h.txt je prázdny.", file=sys.stderr)
            sys.exit(1)
        return token
    except FileNotFoundError:
        print(f"❌ Súbor h.txt neexistuje ({token_file}).", file=sys.stderr)
        sys.exit(1)

TOKEN        = load_token()
BASE         = "https://content.dropboxapi.com/2"
API          = "https://api.dropboxapi.com/2"
HEADERS_AUTH = {"Authorization": f"Bearer {TOKEN}"}


# ══════════════════════════════════════════════════════════════════════════════
#  FOLDER BROWSER
# ══════════════════════════════════════════════════════════════════════════════

def dbx_list_folders(path):
    """Vráti zoznam podpriečinkov na danej Dropbox ceste."""
    arg = {
        "path": "" if path == "/" else path,
        "recursive": False,
        "include_deleted": False,
    }
    r = requests.post(
        f"{API}/files/list_folder",
        headers={**HEADERS_AUTH, "Content-Type": "application/json"},
        data=json.dumps(arg),
        timeout=(10, 30),
    )
    r.raise_for_status()
    data    = r.json()
    entries = data.get("entries", [])

    while data.get("has_more"):
        r = requests.post(
            f"{API}/files/list_folder/continue",
            headers={**HEADERS_AUTH, "Content-Type": "application/json"},
            data=json.dumps({"cursor": data["cursor"]}),
            timeout=(10, 30),
        )
        r.raise_for_status()
        data     = r.json()
        entries += data.get("entries", [])

    folders = sorted(
        [e for e in entries if e[".tag"] == "folder"],
        key=lambda x: x["name"].lower(),
    )
    return folders


def browse_folders():
    """
    Interaktívny terminálový folder browser.
    Vráti vybranú Dropbox cestu alebo None ak užívateľ zruší.
    """
    current = "/"

    while True:
        print()
        print("─" * 55)
        print(f"  📁 Dropbox:{current}")
        print("─" * 55)

        try:
            folders = dbx_list_folders(current)
        except Exception as e:
            print(f"  ⚠  Chyba pri načítaní: {e}")
            folders = []

        # Zostaviť položky menu
        items = []
        if current != "/":
            items.append(("↑  ..", None, "up"))
        for f in folders:
            items.append((f"📁 {f['name']}", f["path_display"], "folder"))
        items.append(("✓  Vybrať TENTO priečinok", current, "select"))
        items.append(("✗  Zrušiť", None, "cancel"))

        for i, (label, _, _) in enumerate(items):
            print(f"  {i:2}.  {label}")

        print()
        try:
            raw = input("  Voľba [číslo]: ").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            return None

        if not raw.isdigit():
            print("  ⚠  Zadaj číslo.")
            continue

        idx = int(raw)
        if idx < 0 or idx >= len(items):
            print("  ⚠  Číslo mimo rozsahu.")
            continue

        _, path, action = items[idx]

        if action == "up":
            current = "/".join(current.rstrip("/").split("/")[:-1]) or "/"
        elif action == "folder":
            current = path
        elif action == "select":
            return current
        elif action == "cancel":
            return None


# ══════════════════════════════════════════════════════════════════════════════
#  UPLOAD
# ══════════════════════════════════════════════════════════════════════════════

def hr_size(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def fmt_time(seconds):
    seconds = int(seconds)
    if seconds < 3600:
        return f"{seconds // 60}:{seconds % 60:02d}"
    return f"{seconds // 3600}:{(seconds % 3600) // 60:02d}:{seconds % 60:02d}"


def print_progress(sent, total, speed_bps, elapsed):
    spd  = f"{hr_size(speed_bps)}/s" if speed_bps else "--"
    eta  = fmt_time((total - sent) / speed_bps) if speed_bps else "--:--"
    line = f"\r  {hr_size(sent)} / {hr_size(total)}   {spd}   {fmt_time(elapsed)} / ~{eta}"
    print(line, end="", flush=True)


def upload_small(local_path, dbx_path):
    size  = os.path.getsize(local_path)
    fname = os.path.basename(local_path)

    headers = {
        **HEADERS_AUTH,
        "Content-Type": "application/octet-stream",
        "Content-Length": str(size),
        "Dropbox-API-Arg": json.dumps({
            "path": dbx_path,
            "mode": "overwrite",
            "autorename": False,
            "mute": True,
        }),
    }

    with open(local_path, "rb") as f:
        class ProgressReader:
            def __init__(self, fh, total):
                self.fh      = fh
                self.total   = total
                self.sent    = 0
                self.t_start = time.monotonic()

            def read(self, n=-1):
                chunk        = self.fh.read(n)
                self.sent   += len(chunk)
                elapsed      = time.monotonic() - self.t_start
                speed        = self.sent / elapsed if elapsed > 0 else 0
                print_progress(self.sent, self.total, speed, elapsed)
                return chunk

        r = requests.post(f"{BASE}/files/upload",
                          headers=headers, data=ProgressReader(f, size),
                          timeout=(15, 120))
    print()
    r.raise_for_status()


def upload_large(local_path, dbx_path):
    size    = os.path.getsize(local_path)
    sent    = 0
    t_start = time.monotonic()

    # Start session
    r = requests.post(
        f"{BASE}/files/upload_session/start",
        headers={**HEADERS_AUTH, "Content-Type": "application/octet-stream",
                 "Dropbox-API-Arg": json.dumps({"close": False})},
        data=b"",
        timeout=(15, 30),
    )
    r.raise_for_status()
    session_id = r.json()["session_id"]

    with open(local_path, "rb") as f:
        while True:
            chunk   = f.read(CHUNK_SIZE)
            if not chunk:
                break
            is_last = (sent + len(chunk) >= size)

            if is_last:
                arg = {
                    "cursor": {"session_id": session_id, "offset": sent},
                    "commit": {"path": dbx_path, "mode": "overwrite",
                               "autorename": False, "mute": True},
                }
                r = requests.post(
                    f"{BASE}/files/upload_session/finish",
                    headers={**HEADERS_AUTH, "Content-Type": "application/octet-stream",
                             "Dropbox-API-Arg": json.dumps(arg)},
                    data=chunk,
                    timeout=(15, 300),
                )
            else:
                arg = {"cursor": {"session_id": session_id, "offset": sent},
                       "close": False}
                r = requests.post(
                    f"{BASE}/files/upload_session/append_v2",
                    headers={**HEADERS_AUTH, "Content-Type": "application/octet-stream",
                             "Dropbox-API-Arg": json.dumps(arg)},
                    data=chunk,
                    timeout=(15, 300),
                )

            r.raise_for_status()
            sent   += len(chunk)
            elapsed = time.monotonic() - t_start
            speed   = sent / elapsed if elapsed > 0 else 0
            print_progress(sent, size, speed, elapsed)

    print()


def upload_file(local_path, dbx_dest_dir):
    fname    = os.path.basename(local_path)
    dbx_path = f"{dbx_dest_dir.rstrip('/')}/{fname}"
    size     = os.path.getsize(local_path)

    print(f"\n→ {local_path}  ({hr_size(size)})")
    print(f"  Cieľ: {dbx_path}")

    if size >= THRESHOLD:
        upload_large(local_path, dbx_path)
    else:
        upload_small(local_path, dbx_path)

    print(f"  ✓ Hotovo")


def collect_files(paths):
    """Vráti zoznam (local_path, rel_root) pre všetky súbory."""
    result = []
    for p in paths:
        p = os.path.abspath(p)
        if os.path.isfile(p):
            result.append((p, os.path.dirname(p)))
        elif os.path.isdir(p):
            parent = os.path.dirname(p)
            for root, dirs, files in os.walk(p):
                dirs.sort()
                for fn in sorted(files):
                    result.append((os.path.join(root, fn), parent))
        else:
            print(f"⚠  Nenájdené: {p}", file=sys.stderr)
    return result


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Dropbox uploader s folder browserom")
    parser.add_argument("paths", nargs="+", help="Súbory alebo priečinky na nahratie")
    parser.add_argument(
        "--dest", default=None,
        help="Cieľový priečinok v Dropboxe – preskočí interaktívny výber",
    )
    args = parser.parse_args()

    files = collect_files(args.paths)
    if not files:
        print("Žiadne súbory na nahratie.", file=sys.stderr)
        sys.exit(1)

    # ── Výber cieľového priečinka ──────────────────────────────────────────
    if args.dest:
        dest = args.dest
    else:
        print(f"\nNájdených {len(files)} súbor(ov). Vyber cieľový priečinok v Dropboxe:")
        dest = browse_folders()
        if dest is None:
            print("Zrušené.")
            sys.exit(0)

    # ── Upload ────────────────────────────────────────────────────────────
    print()
    print(f"Nahrávam {len(files)} súbor(ov)  →  Dropbox:{dest}")
    print("═" * 55)

    ok   = 0
    fail = 0
    for i, (local_path, rel_root) in enumerate(files, 1):
        rel     = os.path.relpath(local_path, rel_root)
        dbx_dir = dest.rstrip("/") + "/" + os.path.dirname(rel)
        dbx_dir = dbx_dir.replace("\\", "/").replace("//", "/")

        print(f"[{i}/{len(files)}]", end="")
        try:
            upload_file(local_path, dbx_dir)
            ok += 1
        except Exception as e:
            print(f"\n  ✗ Chyba: {e}")
            fail += 1

    print("═" * 55)
    print(f"Hotovo: {ok} OK, {fail} chýb")


if __name__ == "__main__":
    main()
