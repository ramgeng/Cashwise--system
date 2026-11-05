# Cashwise backend

FastAPI + SQLAlchemy + Groq + Hindsight. Start it from the project root:

```
uvicorn app.main:app --reload
```

Interactive API docs: http://localhost:8000/docs

## Structure

```
app/
  main.py            app setup: routers, error format, request logs, serves the built frontend
  core/              settings (.env), password hashing + JWT, error format, logging, money helpers
  db/
    platform.py      shared database: users, businesses, memberships
    tenant.py        one database per business: customers, invoices, payments, bills, expenses,
                     cash ledger, memory events, agent log
  services/
    books.py         read access to one business's records
    forecast.py      the cash-flow maths (best / likely / worst from real payment history)
    insights.py      dashboard read-outs: key bill, this week's actions, chart series, timeline
    ingest.py        CSV import: checks every row, then recomputes statuses and the cash ledger
    memory.py        Hindsight memory, one bank per business
    agent.py         the Groq agent loop (recall -> tools -> answer -> retain)
    tools.py         the tools the agent can call
    accounts.py      sign-up, sign-in, businesses, demo account
    demo.py          loads the Malabar Electronics demo data through the same import path
  routes/            HTTP endpoints, grouped: auth, businesses, dashboard, agent, data
  schemas.py         request bodies and their limits
scripts/             command-line helpers (see below)
tests/               pytest suite
storage/             created at first start: platform.db, businesses/<id>.db, .jwt_secret (never commit)
```

## How data is kept apart

- Every business has **its own database file** (`storage/businesses/<id>.db`) and **its own Hindsight memory bank**.
- Every business endpoint needs `Authorization: Bearer <token>` and `X-Business-Id: <id>`.
  The backend checks the signed-in user belongs to that business; otherwise it answers 404.

## Sign-in

- First start creates a demo account: **demo@cashwise.app / demo1234** with the demo business loaded.
  Its memory bank is `malabar-electronics`, the same one used earlier.
- Passwords are hashed with PBKDF2-SHA256. Tokens are JWTs, valid 72 hours (`JWT_HOURS`).

## Sign in with Google, GitHub or Apple

The buttons work once the provider's keys are in `.env`; until then they explain what is missing.
After adding keys, restart the backend. The redirect address to register is
`APP_URL/api/auth/oauth/<provider>/callback`, e.g. `http://localhost:5173/api/auth/oauth/google/callback`
(the frontend dev server forwards it to the backend).

**Google** (free)
1. https://console.cloud.google.com → create a project → APIs & Services → OAuth consent screen (External, add your email as a test user).
2. Credentials → Create credentials → OAuth client ID → Web application.
3. Authorised redirect URI: `http://localhost:5173/api/auth/oauth/google/callback`
4. Copy the client ID and secret into `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`.

**GitHub** (free)
1. GitHub → Settings → Developer settings → OAuth Apps → New OAuth App.
2. Homepage URL `http://localhost:5173`, callback URL `http://localhost:5173/api/auth/oauth/github/callback`.
3. Generate a client secret; copy both into `GITHUB_CLIENT_ID` and `GITHUB_CLIENT_SECRET`.

**Apple** (needs a paid Apple Developer account, and Apple only accepts https addresses, not localhost)
1. developer.apple.com → Identifiers → add a Services ID with Sign in with Apple; set your https domain and
   `https://<your-domain>/api/auth/oauth/apple/callback`.
2. Keys → create a key with Sign in with Apple, download the `.p8` file.
3. Set `APPLE_CLIENT_ID` (the Services ID), `APPLE_TEAM_ID`, `APPLE_KEY_ID`, `APPLE_PRIVATE_KEY_PATH`, and `APP_URL=https://<your-domain>`.

How it works: the browser goes to the provider with a signed, 10-minute `state` plus a one-time cookie;
the provider sends it back with a code; the backend swaps the code for the person's **verified** email,
finds or creates the Cashwise user (linking to an existing account with the same email), and returns
the browser to the app with a Cashwise token in the URL fragment. Accounts created this way have no password.

## Uploading your own records

Order: customers, invoices, payments received, suppliers, bills, payments made, expenses, history.

- Download a template from the dashboard (**Your data**) or `GET /api/data/templates/{kind}`.
- Dates: `2026-11-05`, `05/11/2026`, `05-11-2026` or `5 Nov 2026`. Amounts may include `₹`, `Rs` and commas.
- Leave due dates blank to use the customer's or supplier's terms.
- **Replace all** swaps the whole table; **Add or update** keeps existing rows and updates rows with the same id.
- If any row has a problem, nothing is saved and you get a list of rows and columns to fix.
- After every upload, what is received/owed, invoice and bill status, and the cash ledger are recomputed.
- History events are also sent to the business's Hindsight bank.

## Commands

```
python -m scripts.load_memory            # send the demo business's history to Hindsight and test a recall
python -m scripts.load_memory --reset    # same, deleting the bank first
python -m scripts.reset_demo             # reload the demo records from data/
python -m scripts.ask                    # chat with the agent in the terminal
python -m scripts.ask --baseline         # the same, with no memory
```

Add `--business <id>` to use another business.

## Tests

```
pip install -r requirements-dev.txt
pytest
```

They cover sign-in (including Google, GitHub and Apple with stand-in providers), one business not seeing another's data, uploads and their checks, the demo
forecast numbers, and the agent loop (with a stand-in AI, so no keys are needed).

## Settings (.env)

See `.env.example`. Only `GROQ_API_KEY` and `HINDSIGHT_API_KEY` are needed; everything else has a default.
