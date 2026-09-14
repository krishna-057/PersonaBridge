# Vercel and Supabase deployment

PersonaBridge deploys as two Vercel projects connected to the same GitHub repository.

## Supabase

1. Create a private Supabase project.
2. Run `supabase/migrations/001_personabridge.sql` in the SQL editor.
3. Copy the project URL and service-role key from the API settings.

The migration enables row-level security and grants no access to `anon` or `authenticated`. Only the FastAPI service may use the service-role key. Never add that key to Git, browser code, `NEXT_PUBLIC_*`, screenshots, logs, or issue descriptions.

## API project

- Git repository: `krishna-057/PersonaBridge`
- Root Directory: `services/api`
- Framework preset: Other
- Environment variables:
  - `SUPABASE_URL`
  - `SUPABASE_SERVICE_ROLE_KEY`
  - `CORS_ALLOWED_ORIGINS` set to the exact production web URL

Vercel detects `services/api/index.py` as the FastAPI entry point.

## Web project

- Git repository: `krishna-057/PersonaBridge`
- Root Directory: `apps/web`
- Framework preset: Next.js
- Environment variable: `NEXT_PUBLIC_API_BASE_URL` set to the API project URL

Only `NEXT_PUBLIC_API_BASE_URL` is exposed to the browser. Do not put Supabase credentials in the web project.

## Privacy boundaries

- The public UI is a portfolio demonstration and must not be used for confidential information.
- Messages, approvals, and consented memory candidates are stored in private tables.
- Obvious secrets and payment/authentication terms are excluded from memory candidates.
- Deleting a memory candidate replaces its summary with `[deleted]` and records the deletion time.
- Realtime tokens are short-lived stubs and are not persisted.
