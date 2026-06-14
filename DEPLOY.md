# Deploying AI Trend Predictor

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

## Updating later
Push to `main` → both Render and Vercel auto-redeploy.

## Free-tier notes
- Render free sleeps after 15 min idle; first request after wake is slow (~50s).
- `predictions.db` (SQLite) resets when Render redeploys/sleeps. The live analysis,
  forecasts, trend, and accuracy *reconstruction* all compute from candles and are
  unaffected; only the forward-logged prediction history resets. For permanent
  history, add a Render persistent disk (paid) or a Supabase Postgres DB.
