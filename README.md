# replicas-autoreg

Полный авторег [replicas.dev](https://replicas.dev) (YC S26) — облачные VM для кодинг-агентов (Claude Code / Codex / Cursor / Opencode). Trial: **$100 кредитов на 30 дней, без карты**. Регистрация: только email — **без капчи, без телефона**.

Auth-бэкенд — Supabase GoTrue. Stdlib-only Python 3.9+, без зависимостей.

## Протокол (реверс 14.10.2026)

1. `POST https://mxeqiomwgdgaesecwtct.supabase.co/auth/v1/signup` `{email, password}` (apikey: публичный anon-ключ из JS-бандла app.replicas.dev)
2. Письмо "Confirm Your Signup" → ссылка `https://auth.replicas.dev/auth/v1/verify?token=***&type=signup` (лаг доставки до 15 мин)
3. `POST /auth/v1/verify` `{type: "signup", token_hash: <token>}` — **внимание: query-параметр ссылки называется `token`, а API принимает его как `token_hash`**. Ответ = сессия (access_token 3ч + refresh_token).
4. `PUT /auth/v1/user` `{password}` (Bearer JWT) — ставим свой пароль для логина через UI
5. `POST https://api.replicas.dev/v1/user/signup/initialize` (Bearer JWT) → создаёт организацию
6. `GET /v1/user/organizations` → `org_id`; `GET /v1/organization/subscription` (header `Replicas-Org-Id`) → кредиты
7. `POST /v1/user/api-keys` `{name}` (+ `Replicas-Org-Id`) → ключ `sk_rep_*`
8. Workspace: `POST /v1/replica` `{name, message, environment_id, coding_agent}` — **только через API-ключ**, user JWT = 401

Лимиты: site-wide email rate limit ~15-20 отправок/час (429 `over_email_send_rate_limit`) → регистрация и подтверждение разделены на фазы A/B.

## Быстрый старт

```bash
python extract_anon.py          # достать supabase url + anon key из публичного бандла
cp pool.txt.example data/pool.txt   # свои IMAP-ящики email:password
python reg.py 10                # фаза A: signup-волна (пейсинг 25с, стоп на 429)
# ...подождать 5-15 минут (доставка писем)...
python sweep.py                 # фаза B: confirm → verify → initialize → банк
python stats.py --rotate        # статистика + ротация refresh-токенов
python api_demo.py 0            # E2E: api key → environment → replica → история
```

Опции путей (флаг или env):
- `--home <dir>` / `REPLICAS_HOME` — каталог данных (default `./data`): `anon.key`, `sb_url.txt`, `bank.jsonl`, `used_emails.txt`, `pool.txt`
- `--pool <file>` / `REPLICAS_POOL` — путь к пулу ящиков
- `REPLICAS_IMAP_HOST` / `REPLICAS_IMAP_PORT` — IMAP провайдера пула (default t-online)

## Банк (bank.jsonl)

Поля: `email, mail_pass, password, user_id, org_id, access_token, refresh_token, credit_cents, plan, api_key, stage`.
`stage`: `signed_up` → `banked` (или `dead_token` после неудачного refresh).

Мёртвые/сгоревшие confirm-ссылки: sweep сам шлёт `/auth/v1/resend` — перезапустите sweep через ~10 минут.

## Нюансы

- LLM-токены агентов — BYO (Anthropic API / OpenRouter / Bedrock / Foundry / подписка Claude через `replicas claude-auth`). Кредиты trial покрывают только VM-вычисления (E2B sandbox).
- OpenAPI: https://docs.replicas.dev/openapi.json
- Анонимный ключ и supabase URL — публичные константы фронтенда, `extract_anon.py` достаёт их сам; в репозитории секретов нет.

## Дисклеймер

Только для исследования собственного аккаунта и образовательных целей. Соблюдайте ToS сервиса.

---
[иишко](https://t.me/AlStack) — каталог халявы, авторегов и AI-инструментов.
