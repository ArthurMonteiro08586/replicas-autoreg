#!/usr/bin/env python
"""Phase A — signup wave. Creates Supabase users (no captcha), marks pool
emails used. Confirmation emails may lag (t-online: up to 15 min) and the
project has a site-wide email rate limit (~15-20/h), so run sweep.py AFTER
this to confirm + bank sessions.

Usage: python reg.py N
"""
import sys, time
import lib

def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    pool = lib.load_pool()
    print(f"pool free: {len(pool)} | target: {n}", flush=True)
    sent = rate_limited = 0
    for e, p in pool:
        if sent >= n: break
        pw = lib.gen_pass()
        st, body = lib.sb("/auth/v1/signup", "POST", {"email": e, "password": pw})
        if st == 200 and isinstance(body, dict) and body.get("id"):
            sent += 1
            print(f"[{e}] signup OK uid={body['id']}", flush=True)
            lib.mark_used(e)
            # save password immediately so sweep can bank it later
            lib.bank_append({"email": e, "mail_pass": p, "password": pw,
                             "user_id": body["id"], "stage": "signed_up",
                             "ts": int(time.time())})
            time.sleep(25)  # pacing vs site-wide email rate limit
            continue
        lib.mark_used(e)
        msg = str(body)[:120]
        print(f"[{e}] signup {st}: {msg}", flush=True)
        if st == 429:
            rate_limited += 1
            if rate_limited >= 3:
                print("email rate limit hit 3x — stopping wave, run sweep.py later", flush=True)
                break
            print("  sleep 600s (rate limit)", flush=True)
            time.sleep(600)
        else:
            rate_limited = 0
            time.sleep(3)
    print(f"RESULT signups_sent={sent}/{n}", flush=True)

if __name__ == "__main__":
    main()
