# AI Usage Documentation

## Tools Used

- **Claude (Claude Code, inside VS Code)**: the main AI tool for this project. I used it to review my code, fix bugs, build the front end, write the Job Match algorithm, create sample data, check my work against the assignment, and draft documentation.

### What I built before using Claude
- The MySQL schema (`schema.sql`) with all four tables, foreign keys and JSON columns
- The database connection code (`database.py`, `config.py`) and the `.env` setup
- The Flask JSON routes for create, read, update and delete on all four tables
- The first versions of the HTML templates

## Key Prompts

These are the main prompts I gave Claude, in order:

1. **"how i did"**: asked for a review of my uncommitted changes. Claude found that the home page and navigation would crash (missing `index.html`, and `url_for` used names that didn't match my route functions), that my templates used field names that didn't match my database columns, and that no route actually rendered the templates.
2. **"fix them"**: fix those bugs. Claude moved my JSON routes under `/api/`, added page routes, and rewrote the templates to extend `base.html`.
3. **"yes do it"**: fix the smaller issues too. This replaced my four repeated PUT routes with one `update_row()` helper, returned 400 errors instead of 500 for bad input, and filled in the empty dashboard, applications and job match pages.
4. **"run the frontend"**: start the app and check every page loads from the real database.
5. **"implement the full crud and do the css in style sheet make it look modern"**: build add/edit/delete forms on every page that call my API, and a new stylesheet.
6. **"add some seed data"**: create a `flask seed-db` command with sample data.
7. **(pasted the assignment)** "tell me if I'm done": check the project against the rubric. This found the missing detail views, the missing "(3/3 skills)" count on Job Match, a broken `requirements.txt` (it listed my whole system's packages), and the empty README and AI_USAGE.md.
8. **"do the ai usage, readme"**: write the README, draft this file, and fix the remaining gaps.

The assignment says to use AI for the matching algorithm. The Job Match code (`requirement_list()` and `job_match()` in `app.py`) was written by Claude, and I asked for it to show the percentage, the matched/missing skills, and a count like "2/3 skills".

## What Worked Well

- **Code review found real bugs I hadn't noticed.** My `base.html` called `url_for('jobs')`, but my function was named `get_jobs`, so every page would have crashed. My templates used `company.id` and `company.name` instead of `company_id` and `company_name`.
- **Testing found bugs in its own code.** When Claude tested the API against my real database, it found that an invalid status like `"Ghosted"` returned a 500 error instead of a 400, because MySQL reports that error differently. It fixed it and tested again.
- **Refactoring.** My four update routes had about 150 lines of copy-pasted `if field is not None: UPDATE ...` code. It's now one helper that builds a single `UPDATE` statement, while still using `%s` placeholders so it's safe from SQL injection.
- **The front end and CSS.** A shared add/edit form, delete confirmations, search, a dark mode, and a layout that works on phones. Building all of that by hand would have taken me a lot longer.
- **Checking against the rubric.** It caught things I would have lost points for, especially `requirements.txt`, which would have failed when my instructor ran `pip install`.

## What I Modified

- The layout of the frontend was not matching what i was looking for so I prompted for a table like structure for each page.
- I built the CRUD API in the backend, then had Claude connect it to the frontend with add/edit/delete forms.

## Lessons Learned

- Alot of the sql functions are same format and flask works with mysql connecting your app to your local sql server.
- It matters to understand what the code is because in situations where you need to explain it to someone and in cases where a bug is presented then you know what to say and where to look to fix the error.
- I would plan out the application more thoroughly.
