# Deploying Trading AI

Two pieces:

- **Frontend** (React/Vite) → **Vercel**
- **Backend** (FastAPI) → **Render** (free web service)

> Note: Supabase can't host a Python web app — it's a database/auth service. It's
> a great *optional* upgrade later for persistent prediction history (Postgres),
> but the app itself runs on Render. Render's free tier is genuinely free; it just
> "sleeps" after ~15 min idle and takes ~50s to wake on the next request.

---

## 1. Backend on Render (do this first — you need its URL for the frontend)

1. Go to **https://render.com** and sign up (free, GitHub login works).
2. **New ➜ Blueprint** → select the `AI-Trend-Predictor` repo.
3. Render reads `render.yaml` and shows the service. It will **prompt for two secrets**:
   - `OPENAI_API_KEY` — your OpenAI key (from `backend/.env`)
   - `ANTHROPIC_API_KEY` — your Claude key (optional; leave blank to use OpenAI only)
4. Click **Apply**. First build takes ~3–5 min.
5. Copy the live URL, e.g. `https://ai-trend-predictor-api.onrender.com`.
6. Test it: open `<that URL>/assets` — you should see the asset list JSON.

## 2. Frontend on Vercel

1. Go to **https://vercel.com** → **Add New ➜ Project** → import the `AI-Trend-Predictor` repo.
2. Vercel reads `vercel.json` (builds the `frontend/` app automatically).
3. Under **Environment Variables**, add:
   - `VITE_API_URL` = your Render backend URL (e.g. `https://ai-trend-predictor-api.onrender.com`)
   - `VITE_FINNHUB_KEY` = your Finnhub key (from `frontend/.env.local`, optional — enables live forex)
4. **Deploy**. Done — your dashboard is live.

> The live candle chart streams **directly from Binance in the browser**, so crypto
> charts work even before the backend is up. The signal/prediction/report panels
> need the backend (`VITE_API_URL`).

---

## 3. Durable history (Turso / libSQL) — keeps the accuracy report alive

By default the app writes to a local `predictions.db` (SQLite). On serverless
(Vercel) and Render's free tier that file lives in ephemeral storage, so the
**accuracy report and paper-trading track record reset on every cold start /
redeploy** — which guts the self-scoring record that's the whole point.

Point the app at a free **[Turso](https://turso.tech)** (libSQL) database and
that history persists durably. No code change — same schema, same queries:

1. Install the CLI and sign up (free): `curl -sSfL https://get.tur.so/install.sh | bash`, then `turso auth signup`.
2. Create a database and a token:
   ```bash
   turso db create trading-ai
   turso db show trading-ai --url        # → libsql://trading-ai-<org>.turso.io
   turso db tokens create trading-ai     # → the auth token
   ```
3. Add these as environment variables (Vercel project → Settings → Environment
   Variables, or Render → Environment), then redeploy:
   - `TURSO_DATABASE_URL` = the `libsql://…` URL
   - `TURSO_AUTH_TOKEN`   = the token

That's it. On boot the app creates the schema in Turso and every prediction,
forecast and paper trade is written there instead of `/tmp`. If the vars are
absent or the database is unreachable, it transparently falls back to local
SQLite, so nothing breaks. (`LIBSQL_URL` / `LIBSQL_AUTH_TOKEN` work as aliases.)

---

## Updating later
Push to `main` → both Render and Vercel auto-redeploy.

## Free-tier notes
- Render free sleeps after 15 min idle; first request after wake is slow (~50s).
- Without a durable database (see **§3**), `predictions.db` (SQLite) resets when
  the host redeploys/sleeps or a serverless function cold-starts. The live
  analysis, forecasts, trend, and accuracy *reconstruction* all compute from
  candles and are unaffected; only the forward-logged prediction history,
  paper-trading book, and the backtest's logged inputs reset. Set
  `TURSO_DATABASE_URL` + `TURSO_AUTH_TOKEN` to keep them permanently.
