# Changelog

All notable changes to Pombo CDN are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0] - 2026-11-12

### Added
- **All-in-One Container Architecture**:
  - Combined Debian Bookworm (`python:3.12-slim-bookworm`), Nginx, Gunicorn, and Supervisor into a single container.
  - Automated boot lifecycle via `entrypoint.sh` executing migrations, static file collection, and SQLite WAL pragmas.
  - Built-in container healthcheck via `/health/` endpoint probing HTTP status every 30 seconds.
- **Direct-to-Disk Streaming Engine**:
  - Implemented Nginx `X-Accel-Redirect` delivery pipeline. Django authorizes tokens and passes internal headers; Nginx handles heavy streaming directly from disk via kernel `sendfile`.
  - Full support for HTTP Range Requests (RFC 7233) allowing audio and video seeking/scrubbing without buffering entire files.
- **Dual Storage Mappings**:
  - `storage/uploads`: Writable destination for files uploaded via the web interface.
  - `storage/external`: Read-only host directory mapping allowing indexing, browsing, and sharing of existing files without disk duplication.
  - Full hierarchical folder tree browsing in File Manager with breadcrumb navigation, subfolder traversal (`..`), and automatic on-the-fly registration.
  - Enabled symlink following (`followlinks=True`) supporting deeply nested or symlinked media library datasets (Jellyfin/Plex).
  - Physical file deletion: Removing uploaded files physically deletes them from host storage, immediately reclaiming disk space.
- **Shareable Link Engine**:
  - Token-based delivery with cryptographically random tokens (`/d/<token>/` for raw stream, `/s/<token>/` for web presentation).
  - Infinite links without count or time constraints.
  - Click/download count limits (automatic expiration after $X$ downloads).
  - Time-based expiration presets (1 hour, 24 hours, 7 days, 30 days) and custom date/time deadlines.
  - Combined rules (expires when either time runs out OR click limit is reached).
  - Expiration landing page (`/link-expired/`) informing users when links are invalidated.
- **Bilingual Interface (EN-US / PT-BR)**:
  - Real-time language switcher (`EN-US | PT-BR`) on login screen, main dashboard top bar, and public download pages.
  - Session-based language persistence with fallback to `DEFAULT_LANGUAGE` environment variable.
- **User Management & Role Permissions**:
  - Custom User model decoupled from default Django admin.
  - Granular permission flags: `can_upload`, `can_create_links`, `can_access_external`, `can_delete`, and `can_manage_users`.
  - Automated initial superuser generation via `initadmin` management command and environment variables (`ADMIN_USERNAME`, `ADMIN_PASSWORD`, `ADMIN_EMAIL`).
- **Session Persistence ("Remember Login")**:
  - Checkbox on login screen enabling 30-day persistent session cookies (`set_expiry(2592000)`).
  - Standard session expiration on browser close (`set_expiry(0)`) when unchecked.
  - Client-side username caching via `localStorage` for rapid re-authentication.
  - Minimalist monochromatic SVG password visibility toggle ("olhinho") on login password field.
- **Favicon & System Branding**:
  - Vector SVG favicon (`/static/favicon.svg`) matching the official pigeon mark configured across all system templates and served directly in Nginx and Django.
- **Mobile Responsive Drawer Navigation**:
  - Off-canvas slide-out sidebar drawer with dark blur backdrop for viewports below 768px.
  - Mobile top bar header with SVG hamburger toggle and brand badge.
  - Responsive table wrappers, mobile-friendly dropzone, and responsive action dialogs.
- **Two-Tier Loading System**:
  - Full-screen preloader (`#appPreloader`) on initial page load, F5 refresh, login submit, logout, and language switching.
  - Localized content-box spinner (`#mainContentBody`) during tab navigation (Overview, Upload, Explorer, Links, Users, Logs) eliminating full-page flicker.
- **Audit Logging System**:
  - Dedicated audit log database recording Link Creation, Downloads, Uploads, Deletions, Authentication attempts, and System Errors.
  - One-click "Copy Logs" formatted text export to clipboard.
  - Safe log purge dialog with custom modal confirmation.
- **Automated CI/CD**:
  - GitHub Actions workflow (`.github/workflows/docker-publish.yml`) building and publishing images to GitHub Container Registry (`ghcr.io/thalisonnunes20/pombo:latest` and `:v1.0.0`).

### Security
- **Multi-Tiered Rate Limiting**:
  - Login endpoint (`/auth/login/`): Throttled in Nginx to `30r/m burst=20 nodelay`.
  - In-app brute-force lockout: 5 consecutive failed login attempts trigger a 5-minute IP lockout returning HTTP 429 and logging the security event.
  - Download and stream endpoints (`/d/`, `/s/`): Throttled in Nginx to `40r/s burst=30 nodelay`.
  - API endpoints (`/storage/api/`): Throttled in Nginx to `60r/s burst=50 nodelay`.
- **Path Traversal Defense**:
  - Canonical path resolution via `resolve_safe_path()` verifying that all requested paths strictly reside within authorized storage roots (`uploads` or `external`). Directory traversal attempts (`../`) are blocked with HTTP 403.
- **Stored XSS & Content Protection**:
  - Strict MIME whitelist (`image/jpeg`, `image/png`, `image/webp`, `video/mp4`, `video/webm`, `audio/mpeg`, `application/pdf`) permitted for inline rendering.
  - Dangerous or executable types (`.html`, `.svg`, `.js`, `.sh`, `.exe`, `.bat`) strictly forced to download as `Content-Disposition: attachment` with `X-Content-Type-Options: nosniff`.
- **Hardened Server Headers**:
  - `X-Frame-Options: SAMEORIGIN`
  - `X-Content-Type-Options: nosniff`
  - `X-XSS-Protection: 1; mode=block`
  - `Referrer-Policy: strict-origin-when-cross-origin`
  - `server_tokens off` in Nginx hiding version disclosure.
  - Explicit Nginx location rules denying dotfiles (`.env`, `.git`) and sensitive source files (`.sqlite3`, `.py`, `.sh`, `.log`).

### Fixed
- Fixed container boot failure (`exec /app/entrypoint.sh: permission denied`) by repositioning `chmod +x /app/entrypoint.sh` after `COPY . /app/` and invoking entrypoint via `/bin/sh` in `Dockerfile`.
- Auto-normalized domain inputs in `CSRF_TRUSTED_ORIGINS` to automatically prepend `https://` and `http://`, preventing Django `(4_0.E001)` errors when protocol scheme is omitted.
- Fixed Docker healthcheck reporting `unhealthy` by serving `/health/` directly in Nginx and ensuring `localhost` and `127.0.0.1` are permanently included in `ALLOWED_HOSTS`.
- Reduced Nginx `worker_connections` to 1024 to eliminate resource limit warnings in default container runtimes.
- Fixed "Host Mapped Folder" tab redirecting to Overview: relative links (`?source=external`) were resolved against the site root instead of the current page in the in-panel navigation.
- Percent-encoded `X-Accel-Redirect` paths so files containing `?`, `#`, `%`, spaces or non-ASCII characters are served correctly by Nginx.
- RFC 6266 `Content-Disposition` headers (`filename*=utf-8''`) for filenames with accents or non-Latin characters.
- URL-encoded folder paths in File Manager links (supports names with `&`, `'`, spaces and parentheses).

### Changed
- Standardized UI branding across all templates with monochromatic SVG vector pigeon icon and version badge `v1.0.0`.
- Upgraded documentation in `README.md` (English) and `README.pt-br.md` (Portuguese) with complete environment variable tables, volume mapping guides, and reverse proxy setup instructions.
- Configured `docker-compose.yml` to pull from `ghcr.io/thalisonnunes20/pombo:latest` with optional local build fallback.

