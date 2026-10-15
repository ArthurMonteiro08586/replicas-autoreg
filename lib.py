"""Shared helpers for replicas.dev autoreg. Stdlib only (Python 3.9+).

Data dir: $REPLICAS_HOME or ./data  (anon.key, bank.jsonl, used_emails.txt)
Email pool: $REPLICAS_POOL or ./data/pool.txt — lines of "email:password"
"""
import json, os, re, secrets, string, sys, time, imaplib, email as emaillib
import urllib.request, urllib.parse, urllib.error

def _opt(name, env_name, default):
    """Value from --name argv flag, then ENV, then default."""
    if f"--{name}" in sys.argv:
        i = sys.argv.index(f"--{name}")
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return os.environ.get(env_name, default)

_HERE = os.path.dirname(os.path.abspath(__file__))
BASE = _opt("home", "REPLICAS_HOME", os.path.join(_HERE, "data"))
os.makedirs(BASE, exist_ok=True)
POOL = _opt("pool", "REPLICAS_POOL", os.path.join(BASE, "pool.txt"))
BANK = os.path.join(BASE, "bank.jsonl")
USED = os.path.join(BASE, "used_emails.txt")
ANON_FILE = os.path.join(BASE, "anon.key")
SBFILE = os.path.join(BASE, "sb_url.txt")

API = "https://api.replicas.dev"
IMAP_HOST = os.environ.get("REPLICAS_IMAP_HOST", "secureimap.t-online.de")
IMAP_PORT = int(os.environ.get("REPLICAS_IMAP_PORT", "993"))

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

def sb_url():
    if os.path.exists(SBFILE):
        return open(SBFILE, encoding="utf-8").read().strip()
    return "https://mxeqiomwgdgaesecwtct.supabase.co"

def anon():
    if not os.path.exists(ANON_FILE):
        raise SystemExit("anon.key missing — run: python extract_anon.py")
    return open(ANON_FILE, encoding="utf-8").read().strip()

def http(url, method="GET", body=None, headers=None, timeout=45):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, method=method)
    r.add_header("Content-Type", "application/json")
    for k, v in {**UA, **(headers or {})}.items():
        r.add_header(k, v)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            return resp.status, _j(resp.read().decode(errors="replace"))
    except urllib.error.HTTPError as e:
        return e.code, _j(e.read().decode(errors="replace"))
    except Exception as ex:
        return -1, {"exc": str(ex)[:150]}

def _j(t):
    try: return json.loads(t)
    except Exception: return {"_raw": t[:300]}

def sb(path, method="GET", body=None, jwt=None):
    h = {"apikey": anon()}
    if jwt: h["Authorization"] = "Bearer " + jwt
    return http(sb_url() + path, method, body, h)

def rp(path, method="GET", body=None, jwt=None, org=None, timeout=60):
    h = {}
    if jwt: h["Authorization"] = "Bearer " + jwt
    if org: h["Replicas-Org-Id"] = str(org)
    return http(API + path, method, body, h, timeout)

def gen_pass():
    alpha = string.ascii_letters + string.digits
    return "Rp!" + "".join(secrets.choice(alpha) for _ in range(14)) + "9x"

def banked_emails():
    out = set()
    if os.path.exists(BANK):
        for l in open(BANK, encoding="utf-8"):
            try: out.add(json.loads(l)["email"].lower())
            except Exception: pass
    return out

def bank_append(rec):
    with open(BANK, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

def bank_write(recs):
    with open(BANK, "w", encoding="utf-8") as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

def bank_read():
    if not os.path.exists(BANK): return []
    return [json.loads(l) for l in open(BANK, encoding="utf-8") if l.strip()]

def mark_used(e):
    with open(USED, "a", encoding="utf-8") as f:
        f.write(e + "\n")

def load_pool():
    used = set()
    if os.path.exists(USED):
        used = {l.strip().lower() for l in open(USED, encoding="utf-8") if l.strip()}
    used |= banked_emails()
    out = []
    for line in open(POOL, encoding="utf-8", errors="replace"):
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line: continue
        e, p = line.split(":", 1)
        e = e.strip().lower()
        if e in used: continue
        out.append((e, p.strip()))
    return out

def pool_pwmap():
    m = {}
    if os.path.exists(POOL):
        for line in open(POOL, encoding="utf-8", errors="replace"):
            if ":" in line:
                e, p = line.strip().split(":", 1)
                m[e.lower()] = p.strip()
    return m

LINK_RE = re.compile(
    r'https://(?:[a-z0-9\-]+\.supabase\.co|auth\.replicas\.dev)/auth/v1/verify\?[^"\'\s<>]+')

def imap_links(addr, pw, last=30):
    """All replicas confirm links in mailbox, newest first."""
    links = []
    try:
        M = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
        M.login(addr, pw)
        M.select("INBOX")
        typ, data = M.search(None, "ALL")
        ids = data[0].split()[-last:]
        for num in reversed(ids):
            typ, msgd = M.fetch(num, "(RFC822)")
            if not msgd or not msgd[0]: continue
            msg = emaillib.message_from_bytes(msgd[0][1])
            tag = (str(msg.get("Subject", "")) + str(msg.get("From", ""))).lower()
            if "replicas" not in tag: continue
            body = ""
            parts = msg.walk() if msg.is_multipart() else [msg]
            for part in parts:
                if part.get_content_type() in ("text/plain", "text/html"):
                    body += (part.get_payload(decode=True) or b"").decode(errors="replace")
            for m in LINK_RE.finditer(body):
                lnk = m.group(0).replace("&amp;", "&")
                if lnk not in links: links.append(lnk)
        M.logout()
    except Exception as ex:
        print(f"    imap err {addr}: {str(ex)[:80]}", flush=True)
    return links

def verify_link(link):
    """Exchange a confirm link for a GoTrue session. NOTE: the URL query param
    is named `token` but the verify API expects it as `token_hash`."""
    q = urllib.parse.parse_qs(urllib.parse.urlparse(link).query)
    payload = {"type": (q.get("type") or ["signup"])[0]}
    th = (q.get("token_hash") or q.get("token") or [None])[0]
    if th: payload["token_hash"] = th
    st, sess = sb("/auth/v1/verify", "POST", payload)
    if st == 200 and isinstance(sess, dict) and sess.get("access_token"):
        return sess
    return None

def resend_signup(e):
    return sb("/auth/v1/resend", "POST", {"type": "signup", "email": e})

def init_and_org(jwt):
    """signup/initialize -> org_id, credit cents, plan."""
    st1, _ = rp("/v1/user/signup/initialize", "POST", None, jwt)
    st2, b2 = rp("/v1/user/organizations", "GET", None, jwt)
    org_id = None
    try: org_id = b2["organizations"][0]["id"]
    except Exception: pass
    cents = plan = None
    if org_id:
        st3, b3 = rp("/v1/organization/subscription", "GET", None, jwt, org_id)
        try: cents = b3["credit"]["creditCents"]
        except Exception: pass
        if isinstance(b3, dict): plan = b3.get("plan")
    return st1, org_id, cents, plan
