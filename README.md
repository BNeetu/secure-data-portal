# 🔒 Secure Data Portal

A secure, organization-grade dashboard portal that lets administrators upload
Excel files and instantly generates live KPIs, charts, and tables for every
signed-in user. Local development uses file-backed stores; cloud deployments
can use Supabase for persistent users, audit events, dashboard data, and files.

Built with **FastAPI** (Python) + **React** (Vite).

---

## ✅ What this covers

| Requirement | How it's implemented |
|---|---|
| Secure login | Username + password, bcrypt-hashed, JWT access/refresh tokens |
| Role-based access | `admin`, `manager`, `viewer` — enforced on every protected endpoint |
| Excel upload → dashboard | Admin-only upload; backend parses in-memory and returns chart-ready JSON |
| Auto-refresh on new upload | WebSocket (`/data/ws/live`) pushes the new dataset to every connected browser instantly |
| Persistence | Local runs use JSON and memory; cloud runs use Supabase Postgres and private Storage |
| MFA / OTP | TOTP via Google/Microsoft Authenticator (RFC 6238), QR code shown on first login |
| Strong password policy | 12+ chars, upper/lower/digit/symbol enforced server-side |
| Session timeout | 15-minute access tokens, 15-minute idle auto-logout with a warning modal |
| HTTPS/SSL | nginx config included (`/nginx/nginx.conf`) — terminates TLS, proxies to the app |
| IP whitelisting | **Two layers**: nginx `geo` block (rejects before reaching Python) + FastAPI middleware (`ALLOWED_IPS` env var) |
| Account lockout | 5 failed attempts → 15-minute lockout, admin can unlock manually |
| Audit logs | Every login, failure, lockout, upload, and IP block is logged to `audit_log.jsonl`, viewable in the Admin panel |
| Brute-force / suspicious activity | Failed-attempt counter + lockout; audit log surfaces patterns for review |

---

## 📁 Project Structure

```
secure_portal/
├── backend/
│   ├── app/
│   │   ├── main.py              ← FastAPI entrypoint
│   │   ├── schemas.py           ← Pydantic request/response models
│   │   ├── seed_admin.py        ← CLI script to create the first admin
│   │   ├── core/
│   │   │   ├── config.py        ← All settings, loaded from .env
│   │   │   ├── security.py      ← Password hashing, JWT, TOTP
│   │   │   ├── user_store.py    ← Supabase cloud store + local JSON fallback
│   │   │   ├── data_store.py    ← Supabase cloud store + local memory fallback
│   │   │   ├── audit.py         ← Append-only security event log
│   │   │   ├── deps.py          ← Auth dependencies (current user, role checks)
│   │   │   └── ip_allowlist.py  ← App-level IP restriction middleware
│   │   ├── routers/
│   │   │   ├── auth.py          ← Login, MFA, refresh, user management
│   │   │   ├── data.py          ← Upload, dashboard fetch, live WebSocket
│   │   │   └── audit.py         ← Audit log viewer (admin only)
│   │   └── utils/
│   │       ├── excel_engine.py  ← Generic Excel → dashboard JSON processor
│   │       └── watcher.py       ← Background file-watch + cleanup tasks
│   ├── requirements.txt
│   ├── .env.example             ← Copy to .env and configure
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── App.jsx              ← Router
│   │   ├── main.jsx             ← Entry point
│   │   ├── pages/
│   │   │   ├── Login.jsx        ← Password + MFA/QR flow
│   │   │   ├── Dashboard.jsx    ← Live charts, KPIs, table
│   │   │   └── Admin.jsx        ← User management + audit log viewer
│   │   ├── components/
│   │   │   ├── ProtectedRoute.jsx
│   │   │   ├── UploadWidget.jsx
│   │   │   ├── ChartKit.jsx     ← Shared chart styling/components
│   │   │   └── IdleWarningModal.jsx
│   │   ├── context/AuthContext.jsx  ← Login state, idle timeout
│   │   └── api/
│   │       ├── client.js        ← Axios with auto token refresh
│   │       └── useLiveDashboard.js  ← WebSocket hook for live updates
│   ├── package.json
│   └── Dockerfile
├── nginx/nginx.conf             ← Reverse proxy + IP allowlist + SSL
├── docker-compose.yml
├── start.sh / start.bat         ← One-command local startup
└── README.md
```

---

## 🚀 Quick Start (Local Development)

### Option 1 — One command

**Mac/Linux:**
```bash
./start.sh
```

**Windows:**
```
start.bat
```

This installs dependencies, prompts you to create the first admin account,
and launches both servers.

### Option 2 — Manual

**Backend:**
```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                  # then edit .env
python -m app.seed_admin                               # create the first admin
uvicorn app.main:app --reload --port 8000
```

**Frontend** (new terminal):
```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:3000**

---

## Vercel + Supabase Setup

The Vercel deployment uses Supabase because Vercel Functions cannot persist
the app's local JSON files, uploads, or in-memory datasets across instances.

1. Create a Supabase project and run `backend/supabase_schema.sql` in its SQL Editor.
  This creates the required tables and the private `portal-uploads` bucket.
2. In Vercel, add these variables to the **backend service** for Production and Preview:
  `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_STORAGE_BUCKET=portal-uploads`,
  `JWT_SECRET`, `ENV=production`, and `MFA_REQUIRED=true`.
3. Keep `SUPABASE_SERVICE_ROLE_KEY` server-side. Never expose it as a `VITE_` variable
  or put it in frontend code.
4. From PowerShell in `backend/`, create a Python 3.12 environment and install
  dependencies, then set the Supabase URL and legacy service-role key in that
  terminal and run the admin seeder:

  ```powershell
  py -3.12 -m venv .venv
  .\.venv\Scripts\python.exe -m pip install -r requirements.txt
  $env:SUPABASE_URL = "https://<project-ref>.supabase.co"
  $env:SUPABASE_SERVICE_ROLE_KEY = "<service-role-key>"
  .\.venv\Scripts\python.exe -m app.seed_admin
  ```

  The script prompts for the admin username and password. Never paste the
  service-role key or password into chat or commit them to Git.
5. Redeploy the Vercel project after setting its environment variables.

Uploads are limited to 4 MB because Vercel Functions reject request bodies above
4.5 MB. Supabase stores original workbooks privately and dashboard JSON in Postgres.
The live dashboard also polls the database so updates work across function instances.
Expired uploads are removed when data is accessed; serverless deployments do not
run the local background file watcher or periodic sweeper.

---

## 🔑 First Login

1. Run `python -m app.seed_admin` (done automatically by `start.sh`/`start.bat`).
2. Enter a username and a password meeting the policy (12+ chars, mixed case, digit, symbol).
3. The script prints a TOTP secret and provisioning URI.
4. Go to the login page, sign in with that username/password.
5. On first login, a **QR code appears automatically** — scan it with Google
   Authenticator or Microsoft Authenticator, then enter the 6-digit code.
6. You're in. From then on, every login asks for username + password + the
   6-digit code from your authenticator app.

---

## 🌐 Restricting Access to a Specific IP

You said you'll provide the final IP later — here's exactly where to put it
when you have it. **Two places, for two layers of defense:**

### Layer 1 — Backend (`.env`)
```env
ALLOWED_IPS=203.0.113.42
```
Multiple IPs or ranges: `ALLOWED_IPS=203.0.113.42,198.51.100.0/24`
Leave empty during local development to disable the restriction.

### Layer 2 — nginx (`nginx/nginx.conf`)
```nginx
geo $allowed_ip {
    default 0;
    203.0.113.42  1;     # <-- put the real IP here
}
```

Both layers read from config, not code — no redeployment needed, just edit
the value and restart (`uvicorn` reload picks up `.env` automatically in
dev; in production, restart the service / `nginx -s reload`).

---

## 📊 Dashboard Data and Retention

- Uploaded Excel files are processed with pandas. With Supabase configured,
  processed dashboard JSON is stored in Postgres and original workbooks are
  kept in the private Storage bucket for multi-file merging.
- `UPLOAD_RETENTION_HOURS` controls expiry. In serverless mode, expired uploads
  are pruned when a data-list request runs; local mode uses the background sweeper.
- The frontend polls the persistent file list every 15 seconds. WebSocket updates
  are best-effort because connections can land on different function instances.

---

## 🛡️ Security Notes for Production

- [ ] Generate a real `JWT_SECRET`: `python -c "import secrets; print(secrets.token_urlsafe(48))"`
- [ ] Set `ALLOWED_IPS` in `backend/.env` to the real office IP
- [ ] Set the matching IP in `nginx/nginx.conf`
- [ ] Get a real SSL certificate (e.g. `certbot --nginx`) and update the cert paths
- [ ] Set `ENV=production` in `.env`
- [ ] Review `CORS_ORIGINS` — restrict to your real frontend domain
- [ ] Back up the Supabase project data; it contains user accounts, audit events,
  dashboard records, and upload metadata.
- [ ] Consider rotating `JWT_SECRET` periodically (this invalidates all
      sessions, which is expected)

---

## 🐳 Docker Deployment

```bash
cp backend/.env.example backend/.env   # edit it first!
docker-compose up -d --build
```

Then create the first admin inside the running container:
```bash
docker exec -it sdp-backend python -m app.seed_admin
```

---

## 🔍 API Reference

Visit `http://localhost:8000/docs` for the full interactive Swagger UI.

Key endpoints:
| Method | Path | Access |
|---|---|---|
| POST | `/auth/login` | Public |
| POST | `/auth/mfa/verify` | Public (with temp token) |
| POST | `/auth/refresh` | Public (with refresh token) |
| GET | `/auth/me` | Authenticated |
| POST | `/auth/users` | Admin only |
| GET | `/auth/users` | Admin only |
| POST | `/auth/users/{username}/unlock` | Admin only |
| POST | `/data/upload` | Admin only |
| GET | `/data/dashboard` | Authenticated |
| WS | `/data/ws/live` | Authenticated (token via query param) |
| GET | `/audit` | Admin only |

---

## ⚠️ Known Limitations (by design, per requirements)

- **Stateless JWT logout**: logging out clears the token client-side; the
  token technically remains valid until it expires (max 15 min for access
  tokens). A server-side token blocklist is not implemented.
- **Single dataset at a time**: uploading a new file replaces the old one
  immediately for everyone, with no version history (matches "no historical
  records" requirement exactly).
- **TOTP only**: no SMS/email OTP fallback is wired up yet — the structure
  (`core/security.py`) is ready to extend if you later want to add that.
