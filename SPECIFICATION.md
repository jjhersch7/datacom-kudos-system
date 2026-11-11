# Kudos System Specification

**Project:** Datacom internal employee portal — Kudos feature  
**Method:** Spec-driven development  
**Status:** Reviewed and approved for implementation (prototype scope)

## 1. Initial Feature Request (Step 1)

> Create a feature for our internal web app that allows users to give 'kudos' to their colleagues. A user should be able to select another user from a list, write a short message of appreciation, and submit it. There should also be a public feed on the main dashboard where all recently submitted kudos are visible.

### Initial AI-Generated Requirements (Before Review)

1. An authenticated employee selects a colleague from a user list.
2. The employee writes a short appreciation message (maximum 500 characters).
3. On submission, the message is stored with sender, recipient, and timestamp.
4. The dashboard displays recent kudos, newest first.
5. The service validates input and handles failed requests.

**Initial design proposal:** `Users(id, name, email, role, password_hash)` and `Kudos(id, sender_id, recipient_id, message, created_at)`, backed by SQLite; browser dashboard with JSON APIs.

## 2. Architect Review and Refinements (Step 2)

**Gap identified:** The initial specification did not include a way to moderate inappropriate or spam content. I amended both the requirements and database design **before implementation**.

### Approved Functional Requirements and User Stories

- **US1 — Log in:** As an employee, I can log in to the internal portal; only authenticated users can use its APIs.
- **US2 — Select colleague:** As an employee, I can choose another employee from a list, excluding myself.
- **US3 — Send kudos:** As an employee, I can submit a nonempty appreciation message of at most 500 characters.
- **US4 — See feed:** As an employee, I can see the newest *visible* kudos on the dashboard, with sender, recipient, message, and date, 20 per page.
- **US5 — Moderate (added by architect):** As an **administrator**, I can hide, restore, or permanently delete inappropriate kudos. A hidden message must disappear from the normal feed immediately.
- **US6 — Record moderation (added by architect):** As an administrator, I can provide a reason for hiding or restoring a post. The application records who moderated it and when.
- **US7 — Prevent misuse (added by architect):** Reject blank/oversized messages, self-kudos, nonexistent recipients, exact duplicate submissions from the same sender to the same recipient within 60 seconds, and bursts exceeding five kudos in 60 seconds.
- **US8 — Responsive UI:** The portal works on desktop and mobile. Messages are shown as plain text, never inserted as HTML.

### Acceptance Criteria

1. Unauthenticated users receive HTTP 401 for protected API requests; non-admin users receive HTTP 403 for moderation routes.
2. The colleague list excludes the logged-in employee.
3. A valid message creates one record and appears in the feed; invalid inputs return HTTP 400 with a readable error.
4. Normal feed requests exclude hidden messages and return at most 20 per page; pages use integer `page` starting at 1.
5. Admins can hide, restore, and delete a kudos record; hidden posts are excluded from ordinary feed queries.
6. Moderation updates set `moderated_by`, `moderated_at`, and `reason_for_moderation`; deletion removes the record.
7. The rate and duplicate guards reject attempts with HTTP 429 and 409 respectively.
8. Tests cover authentication, creation, validation, feed filtering, and authorization.

## 3. Approved Technical Design

### Architecture

Small demonstrator using **Python standard library only**: `http.server` for HTTP/API endpoints, `sqlite3` database, HTML/CSS/JavaScript frontend, and `unittest` tests. No additional packages or cloud services are needed. This is a local prototype, not a production-deployed employee identity system.

### Database Schema

**Users**

| Field | Type | Notes |
|---|---|---|
| id | INTEGER PRIMARY KEY | Identifier |
| name | TEXT NOT NULL | Employee display name |
| email | TEXT UNIQUE NOT NULL | Login |
| password_hash | TEXT NOT NULL | PBKDF2 salted password hash |
| role | TEXT NOT NULL | `employee` or `admin` |

**Kudos**

| Field | Type | Notes |
|---|---|---|
| id | INTEGER PRIMARY KEY | Identifier |
| sender_id | INTEGER NOT NULL REFERENCES users(id) | Sender |
| recipient_id | INTEGER NOT NULL REFERENCES users(id) | Recipient |
| message | TEXT NOT NULL | Length 1–500 after trimming |
| created_at | TEXT NOT NULL | UTC ISO timestamp |
| **is_visible** | **INTEGER NOT NULL DEFAULT 1** | **Added by architect; SQLite boolean (0/1)** |
| moderated_by | INTEGER REFERENCES users(id) | Added by architect; admin ID |
| moderated_at | TEXT | Added by architect; UTC timestamp |
| reason_for_moderation | TEXT | Added by architect; moderation reason |

**Sessions:** `token_hash TEXT PRIMARY KEY`, `user_id INTEGER REFERENCES users(id)`, `expires_at TEXT NOT NULL`. Indexes on `kudos(created_at)`, `kudos(is_visible, created_at)`, and `kudos(sender_id, created_at)`.

### API Endpoints

| Method / Path | Authorization | Purpose |
|---|---|---|
| POST `/api/login` | Public | Log in with email and password; set HttpOnly SameSite cookie |
| POST `/api/logout` | Logged in | End session |
| GET `/api/me` | Logged in | Current user's identity and role |
| GET `/api/users` | Logged in | Colleague selection list |
| GET `/api/kudos?page=1` | Logged in | Paginated public feed (visible only) |
| POST `/api/kudos` | Logged in | Create kudos; JSON `recipient_id`, `message` |
| GET `/api/admin/kudos` | Admin | View latest visible and hidden posts |
| PATCH `/api/admin/kudos/{id}` | Admin | Set `is_visible` and optional `reason` |
| DELETE `/api/admin/kudos/{id}` | Admin | Delete inappropriate post |

Successful JSON endpoints use HTTP 200/201; invalid JSON/inputs use 400, authentication 401, authorization 403, missing records 404, duplicates 409, excessive submissions 429. Do not include passwords or session tokens in API responses.

### Frontend Components

- Login panel: email/password and demonstration account information.
- Dashboard: colleague dropdown, kudos message text area with 500-character limit, submit action, feed, pagination.
- Admin moderation panel: list of kudos with hide/restore/delete actions; reason prompt for visibility changes.
- Responsive styling and accessible form labels/status messages.

### Security and Performance

- Passwords hashed with salted PBKDF2, random session tokens stored as SHA-256 hashes, session cookie HttpOnly and SameSite=Lax.
- Authorization enforced server-side for every protected route; SQL uses parameterized queries.
- Render untrusted messages with `textContent` to avoid script injection; JSON request size limits.
- Browser POST/PATCH/DELETE endpoints verify the request Origin header when present (prototype CSRF mitigation). A production deployment would require HTTPS secure cookies, central SSO, full CSRF protection, audit retention, monitoring, and rigorous security review.
- Feed queries select only 20 records using indexed filters and pagination; the initial prototype does not need a cache.
- Server-side log records unexpected exceptions without exposing sensitive details to browsers.

## 4. Implementation Plan (Step 3)

1. **Approve scope** — Reviewed and added the administrator moderation story and `is_visible` schema column before coding.
2. **Create persistence** — SQLite tables, foreign keys, indexes, seeded demonstration employees; depends on approved schema.
3. **Implement authentication** — Login, logout, sessions, role checks; depends on users table.
4. **Implement kudos APIs** — Validation, duplicate/rate limits, visible feed; depends on authentication and kudos table.
5. **Implement administration APIs** — Hide/restore/delete with recorded moderator information; depends on role checks.
6. **Build frontend** — Responsive form, feed and admin panel; depends on API contracts.
7. **Test** — Automated unit tests for core business logic and routes; manual browser acceptance checks.
8. **Prepare deployment** — Document local run steps, avoid committing runtime database or secrets; initial repository commit and public GitHub repository upload.

### Deployment Notes

Run locally with `python app.py` and open `http://127.0.0.1:8000`. The application creates a local `kudos.db` SQLite file on startup. Default demonstration login credentials are listed in `README.md`. Replace demonstration identities and authentication before any real organizational use. Git repo excludes runtime data via `.gitignore`.

## 5. Architect Decision and Verification

**Approved design:** employee kudos plus administrator moderation, including visibility and moderation audit fields. The specification was reviewed and refined before implementation. Implemented code was validated using automated tests; this demonstration does not establish production readiness or a measured SLA improvement.

**Difference from interactive vibe coding:** Requirements and data model were reviewed first, then implementation followed the approved plan. This exposed the content-moderation gap early, avoiding a more disruptive retrofit.
