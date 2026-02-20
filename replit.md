# Team Management Web Dashboard

## Overview

This is a **Team Management Web Dashboard** built with **Python (Flask)** and **Replit DB** for data storage. It provides a complete team workspace with user management, attendance tracking, task management, customer/payment tracking, department management, profile management, and a notice/notification system. The UI uses **Tailwind CSS** (via CDN) and **Jinja2** templates.

The project was originally scaffolded from a Node.js/React template (evidenced by `package.json`, `drizzle.config.ts`, `tailwind.config.ts`), but the actual running application is a **Python Flask server**. The Node.js/React/Drizzle configuration files are remnants and are **not actively used** by the running application.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Backend: Python Flask
- **Entry point**: `main.py` — contains all routes, business logic, and database operations in a single file.
- **Templating**: Jinja2 templates in the `templates/` directory, extending a shared `base.html` layout.
- **Authentication**: Session-based login using Flask's built-in `session`. Passwords are hashed with `werkzeug.security`. No email-based auth — just username/password.
- **Authorization**: Two roles — `admin` (full control) and `member` (limited to own data). A `login_required` decorator guards protected routes.
- **First-run setup**: If no users exist in the database, the app shows an admin setup page to create the initial admin account.

### Data Storage: Replit DB (Key-Value Store)
- Uses `replit.db` when running on Replit, with a **local JSON file fallback** (`db.json`) for local development.
- Data is stored as JSON structures under these keys:
  - `users` — dict of username → user object (role, department, password hash, profile image as base64, contact)
  - `attendance` — list of attendance records (date, username, time_in, time_out, total_hours)
  - `tasks` — list of task objects (id, title, description, status, assigned_to, assigned_by)
  - `departments` — list of department name strings (defaults: Designers, Menu Upload, Finance, Customer Handling)
  - `customers` — list of customer objects with nested payment history
  - `notices` — list of notice objects (title, message, target, date)
- **Important**: This is NOT a relational database. All data is stored as Python dicts/lists serialized to JSON. There is no SQL, no migrations, no schema enforcement.

### Frontend: Server-Side Rendered HTML
- All pages are rendered server-side using Jinja2 templates.
- **Tailwind CSS** is loaded via CDN (`cdn.tailwindcss.com`) — no build step needed.
- **Chart.js** is included via CDN for potential dashboard charts.
- The layout uses a sidebar navigation pattern with responsive design.
- Profile images are stored as **base64 strings** directly in the database (converted client-side via JavaScript FileReader API).

### Key Pages/Routes
| Route | Purpose |
|-------|---------|
| `/setup` | First-run admin account creation |
| `/login`, `/logout` | Authentication |
| `/admin` | Admin dashboard with stats |
| `/member` | Member dashboard with quick actions |
| `/users` | Admin: manage users (add, delete, reset passwords) |
| `/departments` | Admin: manage departments |
| `/attendance` | Check in/out (members), view all records (admin) |
| `/tasks` | Task CRUD, assignment, status updates |
| `/customers` | Customer management with payment tracking |
| `/notices` | Notification system (admin sends, all can view) |
| `/profile` | Profile editing with image upload |

### Unused/Legacy Files
The following files exist from an earlier template but are **not used** by the running Flask application:
- `package.json` — Node.js dependencies (React, Radix UI, Drizzle, etc.)
- `drizzle.config.ts` — PostgreSQL/Drizzle ORM config
- `tailwind.config.ts` — Tailwind build config (app uses CDN instead)
- Any `client/` or `server/` directories that may exist for a React/Express app

**When making changes, focus on `main.py` and the `templates/` directory.** The `dev` script in `package.json` runs `python main.py`.

### Design Decisions

1. **Single-file backend**: All Flask routes and logic live in `main.py`. This keeps things simple for a small team tool but could be refactored into blueprints if it grows.

2. **Replit DB over PostgreSQL**: Chosen for zero-config simplicity — no database provisioning, no migrations, no SQL. Trade-off: no relational queries, no ACID guarantees, limited scalability.

3. **Base64 image storage**: Profile images are stored as base64 strings in the DB. This avoids file system management but increases DB size. For a small team app, this is acceptable.

4. **CDN-based Tailwind**: Avoids build tooling entirely. The trade-off is slightly larger page loads and no tree-shaking, but it means zero frontend build configuration.

5. **Context processor for auth**: The `inject_user` context processor makes `current_user` and `notifications` available in every template automatically.

## External Dependencies

### Python Packages
- **Flask** — Web framework
- **Werkzeug** — Password hashing (bundled with Flask)
- **replit** — Replit DB client (optional, falls back to local JSON)

### CDN Resources
- **Tailwind CSS** — `https://cdn.tailwindcss.com` (styling)
- **Chart.js** — `https://cdn.jsdelivr.net/npm/chart.js` (charts)

### Environment Variables
- `SESSION_SECRET` — Flask session secret key (falls back to `'super_secret_key'`)
- `DATABASE_URL` — Referenced in `drizzle.config.ts` but **not used** by the Flask app

### No External APIs or Services
- No third-party API keys required
- No email service
- No external authentication providers
- No cloud storage — everything is self-contained in Replit DB or local JSON