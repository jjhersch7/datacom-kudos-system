# Datacom Kudos Portal — Task 2

A local, spec-driven Kudos prototype with employee recognition, moderated public feed, and admin hide/restore/delete controls. Uses **Python's standard library**; no pip installs needed.

## Quick start

```powershell
py app.py
```

Open http://127.0.0.1:8000 in your browser. On Linux/macOS, use `python3 app.py`.

Demo accounts:

| Role | Email | Password |
|---|---|---|
| Employee | alex@example.test | DemoPass123! |
| Employee | jamie@example.test | DemoPass123! |
| Admin | admin@example.test | DemoPass123! |

The app creates `kudos.db` automatically. These credentials are for a **local demonstration only** and must never be used in production.

## Tests

```powershell
py -m unittest discover -s tests -v
```

## Files

- `SPECIFICATION.md` — reviewed and approved requirements, design, and plan
- `app.py` — web server and API routes
- `store.py` — database, validation, moderation business rules
- `static/index.html`, `static/app.js`, `static/styles.css` — user interface
- `tests/test_store.py` — functional and moderation tests
- `.gitignore` — excludes local database and caches

## Limitations

This is an educational prototype, not a deployed company portal. Before production use, integrate SSO, HTTPS, comprehensive CSRF protection, audit logs, centralized monitoring, robust moderation policies, and deployment infrastructure.
