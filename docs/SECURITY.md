# DataPulse Security

## Authentication

### Password Hashing

Passwords are hashed with **Argon2id** via the `argon2-cffi` library using the following parameters:
- Time cost: 2 iterations
- Memory cost: 64 MB
- Parallelism: 2
- Hash length: 32 bytes
- Salt length: 16 bytes (random per hash)

Plaintext passwords are never logged, stored, or included in responses.

### Access Tokens

JWT access tokens are signed with HS256 using the `SECRET_KEY` environment variable. They expire after `ACCESS_TOKEN_EXPIRE_MINUTES` (default: 15 minutes). Tokens include:
- `sub` — user UUID
- `iat` — issued-at timestamp
- `exp` — expiry timestamp
- `type: "access"` — prevents refresh tokens from being used as access tokens

### Refresh Tokens

Refresh tokens are 48-byte cryptographically random values. Only a SHA-256 digest is stored in the database — the raw token is never persisted. On refresh, the stored record is revoked and a new token pair is issued (rotation).

An expired or revoked refresh token is rejected with 401. Logging out revokes the refresh token.

---

## Authorization

Every dataset and report endpoint verifies that the requesting user owns the resource. The check is performed in the service layer, not only in route handlers, ensuring it applies regardless of how a service function is called.

**Explicitly tested:**
- User B cannot view, update, delete, preview, or analyze User A's dataset
- User B cannot view or delete User A's report
- Invalid or expired tokens are rejected with 401

---

## File Upload Security

- **Extension validation:** only `.csv` and `.json` are accepted
- **Size limit:** configurable via `MAX_UPLOAD_SIZE_BYTES` (default: 50 MB)
- **Content never executed:** uploaded files are only read as text by Pandas; no shell commands or dynamic imports
- **Safe filenames:** the original filename is sanitized with `_safe_filename()` before storage (strip `.`, replace unsafe chars, basename only)
- **Path traversal prevention:** `storage/local.py` resolves all paths and verifies they remain within `UPLOAD_DIR` before reading or deleting

---

## Database Security

- All queries go through SQLAlchemy's parameterized query builder; no string interpolation into SQL
- Connection credentials are loaded from environment variables only
- The database user `datapulse` has no superuser privileges

---

## Secrets Management

- `SECRET_KEY` and `DATABASE_URL` must be set via environment variables or `.env`
- `.env` is in `.gitignore` and must never be committed
- `.env.example` contains placeholder values only

---

## CORS

CORS origins are configured via `CORS_ORIGINS`. The default allows `localhost:3000` and `localhost:8000` for development. In production, set this to the exact origin(s) of your frontend.

---

## Logging

- Access tokens and refresh tokens are never logged
- Passwords and secrets are never logged
- Production error responses contain a code and message; no stack traces or internal paths are exposed

---

## Known Limitations

1. **No rate limiting is implemented** beyond configuration documentation. The `AUTH_RATE_LIMIT` setting is defined but not enforced by middleware. Rate limiting should be added (e.g., via `slowapi`) before production deployment.

2. **HS256 tokens** cannot be validated without the shared secret. If tokens need to be validated by multiple independent services, switch to RS256.

3. **Local file storage** has no server-side encryption at rest. Files are stored as-is on the filesystem.

4. **Single-secret rotation** — rotating `SECRET_KEY` invalidates all existing access tokens. A key-rotation strategy (e.g., versioned keys or short expiry) should be planned for production.

5. **This application has not been independently security-audited.** The controls described here reflect implementation intent and reasonable practice; they do not constitute a security guarantee.
