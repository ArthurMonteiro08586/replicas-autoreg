#!/usr/bin/env python
"""Bank stats + refresh-token rotation. JWTs expire in 3h; refresh_token
rolls indefinitely. Run before using banked accounts.

Usage:
  python stats.py            # stats only
  python stats.py --rotate   # refresh all tokens, rewrite bank
"""
import sys, json, time
import lib

def main():
    rotate = "--rotate" in sys.argv
    bank = lib.bank_read()
    banked = [r for r in bank if r.get("stage") == "banked" or r.get("org_id")]
    pending = [r for r in bank if r not in banked]
    credits = sum(r.get("credit_cents") or 0 for r in banked)
    print(f"bank total: {len(bank)} | banked: {len(banked)} | pending sweep: {len(pending)}")
    print(f"credits: {credits}c = ${credits/100:.0f} | with password: {len([r for r in banked if r.get('password')])}")
    if not rotate:
        return
    ok = bad = 0
    for r in banked:
        rt = r.get("refresh_token")
        if not rt: bad += 1; continue
        st, b = lib.sb("/auth/v1/token?grant_type=refresh_token", "POST", {"refresh_token": rt})
        if st == 200 and isinstance(b, dict) and b.get("access_token"):
            r["access_token"] = b["access_token"]
            r["refresh_token"] = b.get("refresh_token") or rt
            ok += 1
        else:
            r["stage"] = "dead_token"
            bad += 1
            print(f"  {r['email']}: refresh {st} {str(b)[:80]}")
        time.sleep(0.5)
    lib.bank_write(bank)
    print(f"ROTATE ok={ok} dead={bad}")

if __name__ == "__main__":
    main()
