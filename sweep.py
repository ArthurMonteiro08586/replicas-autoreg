#!/usr/bin/env python
"""Phase B — confirmation sweep. For every signed-up (unbanked) mailbox:
fetch confirm email via IMAP, verify token -> session, set a known password,
POST /v1/user/signup/initialize (creates org), read subscription, bank full
record. Dead/consumed links trigger /auth/v1/resend automatically — re-run
sweep after ~10 min to pick up resent emails.

Usage: python sweep.py [max_mailboxes]
"""
import sys, time
import lib

def main():
    pwmap = lib.pool_pwmap()
    bank = lib.bank_read()
    by_email = {r["email"].lower(): r for r in bank}
    todo = [r for r in bank if r.get("stage") == "signed_up"]
    # also any used emails missing from bank entirely (legacy runs)
    if __import__("os").path.exists(lib.USED):
        for l in open(lib.USED, encoding="utf-8"):
            e = l.strip().lower()
            if e and e not in by_email:
                todo.append({"email": e})
    if len(sys.argv) > 1: todo = todo[:int(sys.argv[1])]
    print(f"targets: {len(todo)}", flush=True)
    ok = fail = 0
    out = {}
    for t in todo:
        e = t["email"]
        pw = t.get("mail_pass") or pwmap.get(e)
        if not pw:
            print(f"[{e}] no pool pw"); fail += 1; continue
        links = lib.imap_links(e, pw)
        sess = None
        for link in links:
            sess = lib.verify_link(link)
            if sess: break
        if not sess:
            st_r, _ = lib.resend_signup(e)
            why = "all links dead" if links else "no confirm email"
            print(f"[{e}] {why} — resend {st_r}", flush=True)
            fail += 1
            out[e] = t
            continue
        jwt = sess["access_token"]; rt = sess.get("refresh_token")
        uid = sess.get("user", {}).get("id") or t.get("user_id")
        newpw = t.get("password") or lib.gen_pass()
        st_p, _ = lib.sb("/auth/v1/user", "PUT", {"password": newpw}, jwt)
        if st_p != 200: newpw = None
        st1, org_id, cents, plan = lib.init_and_org(jwt)
        rec = {"email": e, "mail_pass": pw, "password": newpw, "user_id": uid,
               "org_id": org_id, "access_token": jwt, "refresh_token": rt,
               "credit_cents": cents, "plan": plan, "init": st1,
               "stage": "banked", "ts": int(time.time())}
        out[e] = rec
        ok += 1
        print(f"[{e}] BANKED org={org_id} credits={cents} plan={plan} init={st1}", flush=True)
        time.sleep(2)
    # rewrite bank: keep all previous records, overlay updates
    merged = {}
    for r in lib.bank_read():
        merged[r["email"].lower()] = r
    merged.update({k: v for k, v in out.items()})
    lib.bank_write(list(merged.values()))
    print(f"SWEEP RESULT ok={ok} fail={fail} bank_total={len(merged)}", flush=True)

if __name__ == "__main__":
    main()
