# RiftAnalyzerGG frontend

A small React + TypeScript app backed by the existing FastAPI application. The
interface is in English. Player lookup, champion/lane filters and report sections
are separate modules so new analysis views can be added independently.

## Run locally

Use Node.js 22.12+ (Node 22 is tested). Start PostgreSQL and the backend first:

```bash
# From the project root
docker compose up -d db
cd backend
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

In a second terminal:

```bash
cd frontend
npm ci
npm run dev
```

Open <http://127.0.0.1:5173>. Vite forwards `/api` to
`http://127.0.0.1:8000`, so local development uses one browser origin without
requiring CORS changes. If the backend uses another port:

```bash
BACKEND_URL=http://127.0.0.1:8001 npm run dev
```

## User flow

1. Enter the player's game name and tagline and select **View report**.
2. Stored accounts load immediately from the local database. A new local account
   is looked up through Riot, then shown with an **Import latest 50 matches** action.
3. Select a champion, lane, or sample size. Each change fetches a fresh backend
   report using those filters. Filters apply **before** the most-recent-games limit.
4. Explore overall win rate, phase comparisons, sidelane observations and
   statistically supported patterns. Empty/small datasets are explained explicitly.
5. Use **Sync latest 50** to refresh the stored match pool. It imports all champions
   and lanes; the selected filters then determine the report, not what gets stored.

The champion list and counts come from all the player's stored ranked games.
Some champions may have no matches on a particular lane; that combination returns
an empty report, not another champion's data. Riot's `MonkeyKing` name is displayed
as Wukong. The lane values map Mid to MIDDLE, Bot to BOTTOM and Support to UTILITY.

Syncing can take minutes. A partial HTTP 200 sync response is treated as incomplete.
The UI preserves the returned offset, respects Retry-After, and offers **Continue
import**. A permanently unavailable match can be explicitly skipped. Previously
stored matches remain available, and retrying is safe because imports are
idempotent. Riot history offsets can shift if new games are played between attempts.

## Structure

```text
src/
  app/                       Page composition
  components/                Shared application shell
  features/player/           Riot ID search form
  features/analysis/
    api.ts                   Typed API operations
    types.ts                 Backend response contracts
    usePlayerReport.ts       Search/filter/import state and request cancellation
    components/              Filters, overview, phase comparison, pattern evidence
  lib/                       HTTP errors and display formatting
  test/                      Synthetic fixtures and test setup
  styles.css                 Responsive layout and shared design tokens
```

Add a new report section under `features/analysis/components` and compose it in
`App.tsx`. Add new API operations in `api.ts`, and keep database/analysis logic in
the backend. The hook cancels superseded reads to prevent stale-filter results.

## Verification

```bash
npm test
npm run build
```

Browser tests cover desktop and mobile, with synthetic API responses and no Riot
requests:

```bash
npx playwright install chromium
npm run test:e2e
```

Alternatively, use an existing Chrome installation:

```bash
CHROME_PATH=/usr/bin/google-chrome npm run test:e2e
```

## Production build

`npm run build` writes static assets to `dist/`. Serve that directory behind a
reverse proxy that forwards `/api` to FastAPI and falls back to `index.html` for
frontend paths. `npm run preview` is a local build preview, not a production server.

`VITE_API_BASE_URL` is optional for a separate public API origin; that API must
then allow the frontend's origin via CORS. Vite's `VITE_*` variables are public
build-time values: keep the Riot API key exclusively in the backend `.env`.

Data limitations, phase conventions and spatial-proxy interpretation are documented
in [backend analysis](../backend/docs/analysis.md).
