#!/usr/bin/env python
"""API demo on a banked account: create API key (sk_rep_*), list environments,
create a replica workspace, poll status + history. Workspace creation works
ONLY with an API key — user JWT is rejected with 401 "Use an API key".

Usage: python api_demo.py [bank_index] [message]
"""
import sys, json, time
import lib

def main():
    idx = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    msg = sys.argv[2] if len(sys.argv) > 2 else "Run `echo E2E_OK && uname -a` in the terminal and report the output."
    bank = [r for r in lib.bank_read() if r.get("org_id")]
    if not bank:
        raise SystemExit("bank empty — run reg.py + sweep.py first")
    rec = bank[idx % len(bank)]
    jwt, org = rec["access_token"], rec["org_id"]
    print(f"account: {rec['email']} org={org}")

    st, b = lib.rp("/v1/user/api-keys", "POST", {"name": f"demo-{int(time.time())}"}, jwt, org)
    if st not in (200, 201) or not b.get("key"):
        print("api-key FAIL:", st, str(b)[:200]); return
    ak = b["key"]
    rec["api_key"] = ak
    print(f"api-key created: {ak[:12]}... ({len(ak)} chars)")

    st, b = lib.rp("/v1/environments", "GET", None, jwt, org)
    envs = b.get("environments") or []
    if not envs:
        print("no environments:", str(b)[:200]); return
    envid = envs[0]["id"]
    print(f"environment: {envs[0].get('name')} {envid}")

    st, b = lib.rp("/v1/replica", "POST", {
        "name": f"demo-{int(time.time())%100000}",
        "message": msg,
        "environment_id": envid,
        "coding_agent": "claude",
        "lifecycle_policy": "archive_when_done",
    }, ak, org)
    print("create replica:", st, str(b)[:300])
    if st not in (200, 201): return
    rid = b["replica"]["id"]
    for i in range(12):
        time.sleep(10)
        st, b = lib.rp(f"/v1/replica/{rid}", "GET", None, ak, org)
        status = b.get("replica", {}).get("status")
        print(f"  [{i}] status={status}")
        if status in ("archived", "failed", "completed"): break
    st, b = lib.rp(f"/v1/replica/{rid}/history", "GET", None, ak, org)
    for ev in (b.get("events") or [])[-6:]:
        print("  ev:", ev.get("type"), str(ev.get("payload"))[:150])
    lib.bank_write([rec if r is rec else r for r in lib.bank_read()])

if __name__ == "__main__":
    main()
