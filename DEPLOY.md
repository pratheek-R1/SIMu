# Deploying to Render

Three services and one database, all defined in [`render.yaml`](render.yaml):

| Service           | Type          | What it is                                       |
| ----------------- | ------------- | ------------------------------------------------ |
| `survivors-api`   | Web (Python)  | FastAPI. Owns the dataset, scoring, ground truth. |
| `survivors-web`   | Web (Node)    | Next.js analyst terminal.                         |
| `survivors-cache` | Key Value     | Seed-derived caches. Optional.                    |
| `survivors-db`    | Postgres      | Sessions, telemetry, reports.                     |

## First deploy

1. Push this repo to GitHub or GitLab.
2. Render Dashboard → **New** → **Blueprint** → select the repo.
3. Render reads `render.yaml` and shows the four resources. Apply.
4. Wait for `survivors-api` to go live. First boot generates the default cohort
   dataset and runs the validation gate, so it takes longer than a restart —
   watch for `dataset <fingerprint> ready` in the logs.

Nothing needs to be typed in: `JWT_SECRET` is generated, `DATABASE_URL` and
`REDIS_URL` are injected from the managed resources, and each web service gets
the other's hostname by reference.

Verify:

```bash
curl https://survivors-api.onrender.com/api/v1/meta/health
```

Then open the `survivors-web` URL and log in.

### If the blueprint rejects the two services referencing each other

`survivors-api` reads the web host for CORS and `survivors-web` reads the API
host for its build. If Render refuses the pair, delete the `CORS_ORIGINS` entry
from `render.yaml`, apply, then set it by hand on `survivors-api` to the web
service's hostname (a bare host is fine — the API assumes `https://`).

## What changed to make this deployable

- **`DATABASE_URL` is accepted verbatim.** Render issues a libpq URL
  (`postgresql://…`, plus `?sslmode=require` on the external one). `config.py`
  rewrites the scheme to `postgresql+asyncpg://` and moves `sslmode` and
  friends into the driver's connect args, which is where asyncpg wants TLS.
- **`CORS_ORIGINS` accepts bare hostnames**, because a Render service reference
  can only yield a host, never a full origin. Schemeless entries become
  `https://`. `localhost:3000` is allowed automatically whenever `ENVIRONMENT`
  is not `production`.
- **The frontend reads `NEXT_PUBLIC_API_HOST`** for the same reason;
  `next.config.mjs` turns it into an origin. An explicit `NEXT_PUBLIC_API_URL`
  still wins.
- **`npm start` no longer pins port 3000**, so `next start` picks up Render's
  `$PORT`.
- **Boot fails loudly** if `ENVIRONMENT=production` and `JWT_SECRET` is still
  the dev default, rather than issuing forgeable tokens.
- **`.next/` and `.env.local` are untracked.** A committed build output would
  have shipped a stale bundle pointing at `localhost:8000`.
- **Supabase is gone.** Report HTML is stored in Postgres only, which is where
  the facilitator endpoints already read it from; there is no object store to
  drift out of sync and no service-role key to leak.

## Free-tier caveats

Read these before putting a cohort in front of it.

- **Free Postgres is deleted 30 days after creation.** A semester outlasts it.
  Move `survivors-db` to a paid plan, or export before it expires.
- **Free web services sleep after 15 minutes idle** and cold-start on the next
  request — and the API rebuilds its dataset on wake. Hit the API once before a
  class starts, or run both web services on Starter.
- **One worker.** `WEB_CONCURRENCY=1` fits the free instance's 512 MB next to
  the generated dataset. Raise it after moving to a paid plan; the Key Value
  cache is what makes more than one worker correct.

## Environment variables

`render.yaml` sets all of these. Full descriptions live in
[`backend/.env.example`](backend/.env.example).

| Variable                            | Notes                                     |
| ----------------------------------- | ----------------------------------------- |
| `DATABASE_URL`                      | From `survivors-db`.                       |
| `REDIS_URL`                         | From `survivors-cache`.                    |
| `JWT_SECRET`                        | Generated. Rotating it logs everyone out.  |
| `CORS_ORIGINS`                      | From the `survivors-web` host.             |
| `ENVIRONMENT`                       | `production`.                              |
| `DEFAULT_COHORT_SEED`               | **Change per cohort.** See below.          |
| `INR_RATE`, `DELIBERATION_SECONDS`  | Tuning.                                    |
| `NEXT_PUBLIC_API_HOST`              | From the `survivors-api` host. Baked in at **build** time — changing it needs a rebuild, not a restart. |

### Per-cohort seeds

`DEFAULT_COHORT_SEED` is the dataset every unassigned student gets. Reuse it
across semesters and the reveal is common knowledge before the second intake
starts. Give each cohort its own seed via `POST /api/v1/admin/cohorts`.

## Local development

Unchanged. The API falls back to SQLite and an in-process cache with no
configuration at all:

```bash
cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload
```

```bash
cd frontend && npm install && npm run dev
```

## Other platforms

`backend/Procfile` and `backend/railway.json` are still here and still valid —
the `DATABASE_URL` normalisation helps on Railway and Heroku for the same
reason it helps on Render.
