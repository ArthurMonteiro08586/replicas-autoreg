#!/usr/bin/env python
"""Extract the public Supabase project URL + anon key from the app.replicas.dev
JS bundle (both are public constants shipped to every browser). Writes
data/sb_url.txt and data/anon.key. Run once before reg.py/sweep.py.

Usage: python extract_anon.py
"""
import os, re, urllib.request
import lib

def get(url, timeout=45):
    r = urllib.request.Request(url, headers=lib.UA)
    with urllib.request.urlopen(r, timeout=timeout) as resp:
        return resp.read().decode(errors="replace")

def main():
    sb = key = None
    seen = set()
    for page in ("https://app.replicas.dev/", "https://app.replicas.dev/auth"):
        try:
            html = get(page)
        except Exception as ex:
            print(f"  page {page} fail: {ex}")
            continue
        chunks = sorted(set(re.findall(r'/_next/static/(?:immutable/)?chunks/[A-Za-z0-9._\-]+\.js', html)))
        print(f"{page}: {len(chunks)} chunks")
        for c in chunks:
            if c in seen: continue
            seen.add(c)
            try:
                t = get("https://app.replicas.dev" + c)
            except Exception as ex:
                print(f"  skip {c}: {ex}")
                continue
            m = re.search(r'https://([a-z0-9]{15,25})\.supabase\.co', t)
            k = re.search(r'eyJ[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{10,}', t)
            if m and not sb:
                sb = m.group(0)
                print(f"  supabase url in {c}")
            if m and k:
                sb, key = m.group(0), k.group(0)
                print(f"  anon key in {c}")
                break
        if key: break
    if not sb or not key:
        raise SystemExit("extraction failed — bundle layout changed; inspect chunks manually")
    open(lib.SBFILE, "w", encoding="utf-8").write(sb)
    open(lib.ANON_FILE, "w", encoding="utf-8").write(key)
    st, b = lib.sb("/auth/v1/settings")
    print(f"sb_url: {sb}")
    print(f"anon.key: {len(key)} chars (not printed)")
    print(f"settings probe: {st} external_email={b.get('external',{}).get('email') if isinstance(b,dict) else '?'}")

if __name__ == "__main__":
    main()
