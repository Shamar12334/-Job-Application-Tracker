# Job Application Tracker

A full-stack web app for keeping track of a job search: the companies you're interested in, the jobs you find, the applications you send, and the people you meet along the way. It also includes a **Job Match** tool that ranks saved jobs by how many of their required skills you have.

Built for COP4751 with **MySQL**, **Python/Flask** and **HTML/CSS/JavaScript**.

## Features

- **Dashboard**: totals, applications by status, and your most recent applications.
- **Full CRUD for all four tables**: companies, jobs, applications and contacts.
  - List pages with live search.
  - Detail pages for every record, with related data (for example a company's jobs and contacts).
  - Add/edit forms with validation. Required fields, dropdowns for foreign keys and enums, and the salary range is checked.
  - Delete with a confirmation dialog that warns when related records will also be removed.
- **Job Match**: enter your skills and see jobs ranked by match percentage, e.g. `75% (3/4 skills)`, with matched and missing skills listed.
- **JSON columns**: job `requirements` (a list of skills) and application `interview_data` (interview rounds, offers, notes).
- **REST API** under `/api/...` that the front end uses for all create, update and delete actions.
- Responsive layout with automatic light and dark themes.

## Tech stack

| Layer | Technology |
|---|---|
| Database | MySQL 8 |
| Backend | Python 3, Flask 3, mysql-connector-python |
| Frontend | Jinja2 templates, HTML, CSS, vanilla JavaScript |
| Config | python-dotenv (`.env` file) |

## Project structure

```
├── app.py               # Flask app: page routes, JSON API routes, CLI commands
├── database.py          # Database connection + init_db()
├── config.py            # Reads DB settings from .env / environment variables
├── schema.sql           # Creates the database and the 4 tables
├── seed.py              # Sample data (flask seed-db)
├── requirements.txt     # Python dependencies
├── .env.example         # Template for your .env file
├── static/
│   ├── style.css        # All styles
│   └── app.js           # Add/edit/delete dialogs, search, notifications
└── templates/
    ├── base.html               # Shared layout + navigation
    ├── index.html              # Home page
    ├── dashboard.html
    ├── companies.html          # list pages...
    ├── jobs.html
    ├── applications.html
    ├── contacts.html
    ├── company_detail.html     # ...and their detail pages
    ├── job_detail.html
    ├── application_detail.html
    ├── contact_detail.html
    ├── job_match.html
    ├── 404.html
    ├── _crud.html              # Form field settings for each table
    └── _detail.html            # Helpers used by the detail pages
```

## Database schema

Four tables, connected with foreign keys. Deleting a parent row removes its children (`ON DELETE CASCADE`).

```
companies 1 ──< jobs 1 ──< applications
    1
    └──< contacts
```

| Table | Key columns |
|---|---|
| `companies` | `company_id` PK, `company_name` (required), industry, website, city, state, notes |
| `jobs` | `job_id` PK, `company_id` FK, `job_title` (required), `job_type` ENUM, salary_min/max, job_url, date_posted, `requirements` JSON |
| `applications` | `application_id` PK, `job_id` FK, `application_date` (required), `status` ENUM, resume_version, cover_letter_sent, `interview_data` JSON |
| `contacts` | `contact_id` PK, `company_id` FK, `contact_name` (required), title, email, phone, linkedin_url, notes |

See [schema.sql](schema.sql) for the full definitions.

## Setup

### 1. Prerequisites
- Python 3.10 or newer
- MySQL 8 server running locally (or a hosted MySQL you can connect to)

### 2. Clone and install

```bash
git clone https://github.com/Shamar12334/-Job-Application-Tracker.git
cd -- -Job-Application-Tracker

python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure the database login

Copy the example settings file and put in your MySQL username and password:

```bash
cp .env.example .env               # Windows: copy .env.example .env
```

```ini
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_mysql_password
DB_NAME=job_tracker
```

`.env` is in `.gitignore`, so your password is never committed.

### 4. Create the database and tables

```bash
flask --app app init-db
```

This runs `schema.sql`, which creates the `job_tracker` database and the four tables. It's safe to run again because every statement uses `IF NOT EXISTS`.

You can also run the script directly: `mysql -u root -p < schema.sql`

### 5. (Optional) Load sample data

```bash
flask --app app seed-db            # only works on an empty database
flask --app app seed-db --reset    # WARNING: deletes all data first, then reseeds
```

This adds 6 companies, 10 jobs, 8 applications (covering every status) and 6 contacts. All names are made up.

### 6. Run the app

```bash
flask --app app run --debug
```

Open <http://127.0.0.1:5000>.

## Using the app

| Page | URL | What it does |
|---|---|---|
| Home | `/` | Totals and a getting-started checklist |
| Dashboard | `/dashboard` | Statistics, status breakdown, recent applications |
| Companies | `/companies`, `/companies/<id>` | List, add, edit, delete; detail shows the company's jobs and contacts |
| Jobs | `/jobs`, `/jobs/<id>` | List, add, edit, delete; detail shows applications for the job |
| Applications | `/applications`, `/applications/<id>` | List, add, edit, delete; detail shows interview rounds and offers |
| Contacts | `/contacts`, `/contacts/<id>` | List, add, edit, delete |
| Job Match | `/job-match` | Rank jobs by how well they match your skills |

Add records in this order: **company → job → application**. Jobs and contacts need a company, and applications need a job.

### How Job Match works

1. Your input (e.g. `Python, SQL, Flask`) is split on commas and lower-cased.
2. Each job's `requirements` JSON is read as a list of skills, also lower-cased. Objects like `{"skills": [...]}` are supported too.
3. Score = matched skills ÷ required skills, shown as a percentage and as a count (`2/3 skills`).
4. Jobs are sorted by score, then by number of matched skills. Jobs with no requirements are skipped.

Matching is exact apart from upper/lower case, so `postgres` doesn't match `PostgreSQL`.

## REST API

All endpoints accept and return JSON. Dates use `YYYY-MM-DD`.

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/companies` | List all companies |
| POST | `/api/companies` | Create (`company_name` required) |
| GET | `/api/companies/<id>` | Get one |
| PUT | `/api/companies/<id>` | Update the fields you send (`null` clears a field) |
| DELETE | `/api/companies/<id>` | Delete (also deletes its jobs, applications and contacts) |

`/api/jobs`, `/api/applications` and `/api/contacts` work the same way. Their required fields are:

- **jobs**: `company_id`, `job_title`
- **applications**: `job_id`, `application_date`
- **contacts**: `company_id`, `contact_name`

Invalid input returns **400** with an `error` message: missing required fields, an unknown ID, a bad date or status, or `salary_min > salary_max`. A missing record returns **404**.

Example:

```bash
curl -X POST http://127.0.0.1:5000/api/jobs \
  -H "Content-Type: application/json" \
  -d '{"company_id": 1, "job_title": "Backend Developer", "job_type": "Full-time",
       "salary_min": 85000, "salary_max": 110000, "requirements": ["Python", "Flask", "SQL"]}'
```

## AI usage

This project was built with help from generative AI. See [AI_USAGE.md](AI_USAGE.md) for the tools, prompts, and what was changed.
