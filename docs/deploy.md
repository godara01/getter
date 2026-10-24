# Staging deployment

Prepared for a small Linux server in Mumbai or Bangalore, managed Neon
Postgres, Cloudflare Pages, and Clerk. No accounts, keys or live domain are
required to validate the configuration. This does not provision infrastructure
or publish production. Practice and legal copy remain subject to launch gates.

## One-time owner setup, in order

1. Merge the Clerk and grading queue PRs before enabling deployment secrets.
   The Compose worker runs `getter_api.worker.WorkerSettings`; the static web
   build needs Clerk support. Keep the remaining task PRs current with master,
   including Alembic merge revisions when independent migrations meet.
2. Create a small **Linux amd64** server in Mumbai or Bangalore. Install Docker
   Engine and Compose **2.30+**, curl and bash. Create a deploy user with a home
   directory and Docker access. Docker access grants root-equivalent power;
   use a dedicated SSH key. Allow inbound SSH from your administration/CI
   network and TCP 80/443 (UDP 443 optional). Do not expose API 8000, Redis
   6379 or a database port. The Compose network uses 172.29.0.0/24; check that
   it does not overlap a server network.
3. Create a separate **Neon staging database**. Enable backups appropriate to
   the chosen free-tier limits and save the TLS connection URL with the
   `postgresql+psycopg://` scheme and `?sslmode=require`. Never reuse a
   production database for staging. There is no Postgres container here.
4. Create a **Cloudflare Pages Direct Upload** project, for example
   `getter-staging`, with production branch `master`. GitHub Actions uploads
   `apps/web/out` using Wrangler; avoid a second automatic Git build. Record
   the account ID and create a scoped token with Account / Cloudflare Pages /
   Edit permission. See [Cloudflare's CI setup](https://developers.cloudflare.com/pages/how-to/use-direct-upload-with-continuous-integration/).
5. Choose the staging API domain, e.g. `api-staging.example.com`. Add an **A**
   record pointing to the server IPv4 address. Add **AAAA** only if IPv6 works.
   Use DNS-only initially so Caddy obtains certificates directly. Ports 80/443
   and persistent Caddy volumes are required for
   [automatic HTTPS](https://caddyserver.com/docs/automatic-https).
   Use the Pages `*.pages.dev` URL or attach a web custom domain in Pages and
   add the DNS record it requests. Update CORS/Clerk origins if that changes.
6. Create a **Clerk staging application**. Set the allowed web origin to the
   exact Pages/custom domain. Record the publishable key, issuer and JWKS URL.
   No Clerk secret API key is used. Configure the hosted sign-up terms link;
   the current legal text is **draft, pending legal review**, not launch-ready.
7. Ensure GitHub Actions can write packages (`GITHUB_TOKEN` has
   `packages: write` in the workflow). Images are tagged
   `ghcr.io/godara01/getter-api:sha-COMMIT`. After the first publish, make the
   package public, or run `docker login ghcr.io` once as the server deploy user
   with a dedicated read-packages token. Never place registry credentials in
   Compose. The automatic workflow token handles publishing, not server pulls.
8. Add the GitHub repository secrets and variables below. Obtain the SSH host
   key fingerprint through the server console/provider and verify it before
   saving a known_hosts entry. Do not trust an unverified `ssh-keyscan` result.
9. Merge to `master` or run **Staging deploy** manually on `master`. Inspect
   logs for image publishing, migrations, container health, public TLS and
   Pages upload. Complete a private offline-model interview before adding
   real model keys. Real model selection still needs expert-graded transcripts.

## GitHub configuration

Repository **secrets** (Settings → Secrets and variables → Actions):

| Secret | Value |
| --- | --- |
| `STAGING_SSH_HOST` | Server hostname or IPv4 address |
| `STAGING_SSH_USER` | Dedicated deploy user |
| `STAGING_SSH_KEY` | Private key whose public half is in that user's authorized_keys |
| `STAGING_SSH_KNOWN_HOSTS` | Verified known_hosts line for STAGING_SSH_HOST |
| `STAGING_ENV` | Filled contents of [.env.staging.example](../.env.staging.example) |
| `CLOUDFLARE_API_TOKEN` | Scoped Pages Edit token |
| `CLOUDFLARE_ACCOUNT_ID` | Cloudflare account ID |

Repository **variables** (public configuration):

| Variable | Example |
| --- | --- |
| `CLOUDFLARE_PAGES_PROJECT` | `getter-staging` |
| `STAGING_API_URL` | `https://api-staging.example.com` |
| `STAGING_CLERK_PUBLISHABLE_KEY` | Clerk staging publishable key |

All values are supplied through environment variables, never substituted into
shell source. Missing server secrets skip SSH deployment with named log lines;
missing Cloudflare secrets or web variables skip Pages build/upload. Image
building and publishing on master use GitHub's built-in token and need no
owner secret. PR runs validate/build but never publish or deploy. Workflow
manual runs on non-master branches also skip external changes.

## What deployment does

`docker-compose.prod.yml` runs API, one arq worker, persistent Redis and Caddy
on the same server. Redis and the worker are extra always-on processes; Caddy
adds TLS termination. No additional paid service or machine is introduced.
Only Caddy publishes ports. The API trusts forwarded client IP headers only
from Caddy's fixed internal IP, supporting waitlist limits without trusting
arbitrary callers. Caddy's certificate/config volumes and Redis data survive
container replacements.

The workflow copies configuration to `~/getter-staging`, with `.env.staging`
restricted to its owner, pulls the immutable image, runs `alembic upgrade head`
as a one-off API container, restarts services, waits for readiness and checks
`https://API_DOMAIN/health/ready`. This endpoint returns 503 on database failure;
`/health` remains the liveness endpoint. Migrations failing stop deployment
before application containers change. Successful deploys save `.current-image`
and `.previous-image` on the server. Back up the database before schema changes.

Validate with no secrets:

```sh
docker compose -f docker-compose.prod.yml config --quiet
bash -n scripts/deploy.sh
cd services/api && uv run pytest -q tests/test_deploy.py
```

A real SSH/TLS/Pages deployment remains an owner acceptance step after the
accounts and secrets exist. Green skip paths do not mean staging is live.

## Rollback

1. On the server, `cd ~/getter-staging` and inspect `.previous-image` and the
   failed workflow's image SHA. Keep the previous Compose/Caddy configuration
   too if changing infrastructure, and restore it from the corresponding Git
   revision before restarting.
2. For an application-only rollback, export the previous image and recreate
   API and worker without rerunning migrations:

   ```sh
   export GETTER_IMAGE="$(cat .previous-image)"
   docker compose --env-file .env.staging -f docker-compose.prod.yml up -d --wait api worker
   curl --fail https://api-staging.example.com/health/ready
   ```

3. Do not automatically downgrade database schemas: use backward-compatible
   migrations. If an old image cannot use the new schema, restore a Neon
   backup/branch into a separate database and update the protected environment
   after reviewing data loss. A failed migration leaves the old app running.
4. Roll back the web separately in Cloudflare Pages by choosing a previously
   successful production deployment. Check the frontend/API contract and
   complete a test interview. Revert the offending commit on master before
   the next automatic deploy.

R2, Resend, Sentry, PostHog, speech accounts and real model keys are not needed
for this text-only prepared deployment; they remain separate roadmap work.
