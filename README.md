# 🔒 Secure Data Portal

A secure, organization-grade dashboard portal that lets administrators upload
Excel files and instantly generates live KPIs, charts, and tables for every
signed-in user — no database, no manual refresh, restricted to specific IPs.

Built with **FastAPI** (Python) + **React** (Vite).

---

## ✅ What this covers

| Requirement | How it's implemented |
|---|---|
| Secure login | Username + password, bcrypt-hashed, JWT access/refresh tokens |
| Role-based access | `admin`, `manager`, `viewer` — enforced on every protected endpoint |
| Excel upload → dashboard | Admin-only upload; backend parses in-memory and returns chart-ready JSON |
| Auto-refresh on new upload | WebSocket (`/data/ws/live`) pushes the new dataset to every connected browser instantly |
| No database | Users live in a JSON file; uploaded data lives in RAM; nothing is persisted permanently |
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
│   │   │   ├── user_store.py    ← JSON-file user storage (no DB)
│   │   │   ├── data_store.py    ← In-memory dataset + WebSocket broadcast
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

## 📊 How the Dashboard Stays "No Database"

- Uploaded Excel files are parsed **entirely in memory** (`pandas.read_excel`
  on the uploaded bytes) — processed into JSON, then that JSON is what's
  actually kept in RAM (`core/data_store.py`).
- The raw file is also saved to disk **temporarily** (so direct re-saves —
  e.g. editing in Excel and hitting Ctrl+S — can be detected and
  auto-broadcast too) but is deleted automatically after `UPLOAD_RETENTION_HOURS`
  (24h by default).
- A new upload **replaces** the current dataset — no history is kept, per
  the "no historical records" requirement.
- The moment a new file is processed, every connected browser receives it
  instantly via WebSocket — nobody needs to refresh.

---

## 🛡️ Security Notes for Production

- [ ] Generate a real `JWT_SECRET`: `python -c "import secrets; print(secrets.token_urlsafe(48))"`
- [ ] Set `ALLOWED_IPS` in `backend/.env` to the real office IP
- [ ] Set the matching IP in `nginx/nginx.conf`
- [ ] Get a real SSL certificate (e.g. `certbot --nginx`) and update the cert paths
- [ ] Set `ENV=production` in `.env`
- [ ] Review `CORS_ORIGINS` — restrict to your real frontend domain
- [ ] Back up `backend/app/data/users.json` somewhere safe (it's the only
      record of who can log in)
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
  tokens). True server-side revocation would need a token blocklist store,
  which would reintroduce persistent storage — flagged here as a deliberate
  tradeoff given the "no database" requirement.
- **Single dataset at a time**: uploading a new file replaces the old one
  immediately for everyone, with no version history (matches "no historical
  records" requirement exactly).
- **TOTP only**: no SMS/email OTP fallback is wired up yet — the structure
  (`core/security.py`) is ready to extend if you later want to add that.
