import datetime
import click
import json
import mysql.connector
from flask import Flask, abort, jsonify, request, render_template
from flask.json.provider import DefaultJSONProvider
from database import init_db, get_db_connection


class JSONProvider(DefaultJSONProvider):
    """Send dates as 2026-11-18 instead of 'Wed, 18 Nov 2026 00:00:00 GMT'."""
    @staticmethod
    def default(o):
        if isinstance(o, (datetime.date, datetime.datetime)):
            return o.isoformat()
        return DefaultJSONProvider.default(o)


app = Flask(__name__)
app.json = JSONProvider(app)

@app.route('/')
def index():
    counts = fetch_all(
        'SELECT (SELECT COUNT(*) FROM companies) AS companies, '
        '(SELECT COUNT(*) FROM jobs) AS jobs, '
        '(SELECT COUNT(*) FROM applications) AS applications, '
        '(SELECT COUNT(*) FROM contacts) AS contacts'
    )[0]
    return render_template('index.html', counts=counts)

@app.cli.command('init-db')
def init_db_command():
    """Initialize the database."""
    init_db()
    print('Initialized the database.')

@app.cli.command('seed-db')
@click.option('--reset', is_flag=True, help='Delete all existing data before seeding.')
def seed_db_command(reset):
    """Fill the database with sample companies, jobs, applications and contacts."""
    from seed import seed
    conn = get_db_connection()
    try:
        counts = seed(conn, reset=reset)
    except RuntimeError as e:
        raise click.ClickException(str(e))
    finally:
        conn.close()
    print('Seeded: ' + ', '.join(f'{n} {table}' for table, n in counts.items()))

# MySQL errors caused by bad input from the client (-> 400, not 500):
# 1048 column cannot be null, 1062 duplicate, 1264 out of range,
# 1265 data truncated (e.g. bad ENUM value), 1292 bad date, 1366 bad number,
# 1406 too long, 1451/1452 foreign key failures.
BAD_INPUT_ERRNOS = {1048, 1062, 1264, 1265, 1292, 1366, 1406, 1451, 1452}

def is_bad_input(e):
    return (isinstance(e, (mysql.connector.IntegrityError, mysql.connector.DataError))
            or (isinstance(e, mysql.connector.Error) and e.errno in BAD_INPUT_ERRNOS))

def update_row(table, id_col, row_id, data, allowed, json_fields=(), label='Record'):
    """Update only the fields present in `data` with a single UPDATE statement.

    A field sent as null clears that column.

    `table`, `id_col` and `allowed` come from our own code, never from the
    request, so building the column list into the SQL string is safe.
    Values still go through %s placeholders.
    """
    if not isinstance(data, dict):
        return jsonify({'error': 'Request body must be JSON'}), 400
    updates = {f: data[f] for f in allowed if f in data}
    if not updates:
        return jsonify({'error': 'No valid fields to update'}), 400
    for f in json_fields:
        if updates.get(f) is not None:
            updates[f] = json.dumps(updates[f])

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(f'SELECT 1 FROM {table} WHERE {id_col} = %s', (row_id,))
        if cursor.fetchone() is None:
            return jsonify({'error': f'{label} not found'}), 404
        set_clause = ', '.join(f'{f} = %s' for f in updates)
        cursor.execute(f'UPDATE {table} SET {set_clause} WHERE {id_col} = %s',
                       (*updates.values(), row_id))
        conn.commit()
        return jsonify({'message': f'{label} updated successfully'})
    except Exception as e:
        conn.rollback()
        if is_bad_input(e):
            return jsonify({'error': f'Invalid value: {e.msg}'}), 400
        print(f"Error updating {table}: {e}")
        return jsonify({'error': f'An error occurred while updating the {label.lower()}'}), 500
    finally:
        cursor.close()
        conn.close()

def salary_error(salary_min, salary_max):
    """Return an error message if the salary range is invalid, else None."""
    for label, value in (('salary_min', salary_min), ('salary_max', salary_max)):
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, int):
            return f'{label} must be a whole number'
        if value < 0:
            return f'{label} cannot be negative'
    if salary_min is not None and salary_max is not None and salary_min > salary_max:
        return 'salary_min cannot be greater than salary_max'
    return None

#   ---------- HTML page routes ----------
def fetch_all(query, params=()):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(query, params)
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def fetch_one_or_404(query, params):
    rows = fetch_all(query, params)
    if not rows:
        abort(404)
    return rows[0]

@app.errorhandler(404)
def not_found(e):
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Not found'}), 404
    return render_template('404.html'), 404

def parse_json_column(value):
    """MySQL JSON columns come back as text; turn them into Python objects."""
    if isinstance(value, (bytes, bytearray)):
        value = value.decode()
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return value
    return value

def company_options():
    """Companies as {value, label} pairs for the form dropdowns."""
    rows = fetch_all('SELECT company_id, company_name FROM companies ORDER BY company_name')
    return [{'value': r['company_id'], 'label': r['company_name']} for r in rows]

@app.route('/companies')
def companies():
    rows = fetch_all('SELECT * FROM companies ORDER BY company_name')
    return render_template('companies.html', companies=rows)

@app.route('/jobs')
def jobs():
    rows = fetch_all(
        'SELECT j.*, c.company_name FROM jobs j '
        'JOIN companies c ON j.company_id = c.company_id ORDER BY j.job_id DESC'
    )
    for row in rows:
        row['requirements'] = parse_json_column(row['requirements'])
    return render_template('jobs.html', jobs=rows, companies=company_options())

@app.route('/contacts')
def contacts():
    rows = fetch_all(
        'SELECT ct.*, c.company_name FROM contacts ct '
        'JOIN companies c ON ct.company_id = c.company_id ORDER BY ct.contact_name'
    )
    return render_template('contacts.html', contacts=rows, companies=company_options())

#   ---------- companies API routes ----------
@app.route('/api/companies', methods=['GET'])
def get_companies():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute('SELECT * FROM companies')
        companies = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()
    return jsonify(companies)
@app.route('/api/companies', methods=['POST'])
def create_company():
    data = request.get_json(silent=True)
    company_name = (data or {}).get('company_name') or (data or {}).get('name')
    if not company_name:
        return jsonify({'error': 'company_name is required'}), 400
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            'INSERT INTO companies (company_name, industry, website, city, state, notes) '
            'VALUES (%s, %s, %s, %s, %s, %s)',
            (company_name, data.get('industry'), data.get('website'),
             data.get('city'), data.get('state'), data.get('notes'))
        )
        conn.commit()
        return jsonify({'message': 'Company created successfully', 'company_id': cursor.lastrowid}), 201
    except Exception as e:
        conn.rollback()
        if is_bad_input(e):
            return jsonify({'error': f'Invalid value: {e.msg}'}), 400
        print(f"Error creating company: {e}")
        return jsonify({'error': 'An error occurred while creating the company'}), 500
    finally:
        cursor.close()
        conn.close()
@app.route('/api/companies/<int:company_id>', methods=['GET'])
def get_company(company_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute('SELECT * FROM companies WHERE company_id = %s', (company_id,))
        company = cursor.fetchone()
    except Exception as e:
        print(f"Error fetching company: {e}")
        company = None
    finally:
        cursor.close()
        conn.close()
    if company:
        return jsonify(company)
    else:
        return jsonify({'error': 'Company not found'}), 404
@app.route('/api/companies/<int:company_id>', methods=['PUT'])
def update_company(company_id):
    data = request.get_json(silent=True)
    if data and 'name' in data and 'company_name' not in data:
        data['company_name'] = data['name']  # accept the old key too
    return update_row('companies', 'company_id', company_id, data,
                      ['company_name', 'industry', 'website', 'city', 'state', 'notes'],
                      json_fields=(), label='Company')

@app.route('/api/companies/<int:company_id>', methods=['DELETE'])
def delete_company(company_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('DELETE FROM companies WHERE company_id = %s', (company_id,))
        conn.commit()
        if cursor.rowcount == 0:
            return jsonify({'error': 'Company not found'}), 404
        return jsonify({'message': 'Company deleted successfully'})
    except Exception as e:
        conn.rollback()
        if is_bad_input(e):
            return jsonify({'error': f'Invalid value: {e.msg}'}), 400
        print(f"Error deleting company: {e}")
        return jsonify({'error': 'An error occurred while deleting the company'}), 500
    finally:
        cursor.close()
        conn.close()
#   -----------jobsroutes ----------------
@app.route('/api/jobs', methods=['GET'])
def get_jobs():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute('SELECT * FROM jobs')
        jobs = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()
    return jsonify(jobs)
@app.route('/api/jobs', methods=['POST'])
def create_job():
    data = request.get_json(silent=True)
    if not data or not data.get('company_id') or not data.get('job_title'):
        return jsonify({'error': 'company_id and job_title are required'}), 400
    error = salary_error(data.get('salary_min'), data.get('salary_max'))
    if error:
        return jsonify({'error': error}), 400
    requirements = data.get('requirements')
    if requirements is not None:
        requirements = json.dumps(requirements)
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            'INSERT INTO jobs (company_id, job_title, job_type, salary_min, salary_max, job_url, date_posted, requirements) '
            'VALUES (%s, %s, %s, %s, %s, %s, %s, %s)',
            (data.get('company_id'), data.get('job_title'), data.get('job_type'),
             data.get('salary_min'), data.get('salary_max'), data.get('job_url'),
             data.get('date_posted'), requirements)
        )
        conn.commit()
        return jsonify({'message': 'Job created successfully', 'job_id': cursor.lastrowid}), 201
    except Exception as e:
        conn.rollback()
        if is_bad_input(e):
            return jsonify({'error': f'Invalid value: {e.msg}'}), 400
        print(f"Error creating job: {e}")
        return jsonify({'error': 'An error occurred while creating the job'}), 500
    finally:
        cursor.close()
        conn.close()
@app.route('/api/jobs/<int:job_id>', methods=['GET'])
def get_job(job_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute('SELECT * FROM jobs WHERE job_id = %s', (job_id,))
        job = cursor.fetchone()
    finally:
        cursor.close()
        conn.close()
    if job:
        return jsonify(job)
    else:
        return jsonify({'error': 'Job not found'}), 404
@app.route('/api/jobs/<int:job_id>', methods=['PUT'])
def update_job(job_id):
    data = request.get_json(silent=True)
    if isinstance(data, dict) and ('salary_min' in data or 'salary_max' in data):
        # Compare against the saved value for whichever side wasn't sent.
        current = fetch_all('SELECT salary_min, salary_max FROM jobs WHERE job_id = %s', (job_id,))
        if current:
            error = salary_error(data.get('salary_min', current[0]['salary_min']),
                                 data.get('salary_max', current[0]['salary_max']))
            if error:
                return jsonify({'error': error}), 400
    return update_row('jobs', 'job_id', job_id, data,
                      ['company_id', 'job_title', 'job_type', 'salary_min', 'salary_max', 'job_url', 'date_posted', 'requirements'],
                      json_fields=('requirements',), label='Job')

@app.route('/api/jobs/<int:job_id>', methods=['DELETE'])
def delete_job(job_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('DELETE FROM jobs WHERE job_id = %s', (job_id,))
        conn.commit()
        if cursor.rowcount == 0:
            return jsonify({'error': 'Job not found'}), 404
        return jsonify({'message': 'Job deleted successfully'})
    except Exception as e:
        conn.rollback()
        if is_bad_input(e):
            return jsonify({'error': f'Invalid value: {e.msg}'}), 400
        print(f"Error deleting job: {e}")
        return jsonify({'error': 'An error occurred while deleting the job'}), 500
    finally:
        cursor.close()
        conn.close()

#   ----------- applications routes ------
@app.route('/api/applications', methods=['GET'])
def get_applications():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute('SELECT * FROM applications')
        applications = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()
    return jsonify(applications)

@app.route('/api/applications', methods=['POST'])
def create_application():
    data = request.get_json(silent=True)
    if not data or not data.get('job_id') or not data.get('application_date'):
        return jsonify({'error': 'job_id and application_date are required'}), 400
    interview_data = data.get('interview_data')
    if interview_data is not None:
        interview_data = json.dumps(interview_data)
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            'INSERT INTO applications (job_id, application_date, status, resume_version, cover_letter_sent, interview_data) '
            'VALUES (%s, %s, %s, %s, %s, %s)',
            (data.get('job_id'), data.get('application_date'), data.get('status', 'Applied'),
             data.get('resume_version'), data.get('cover_letter_sent'), interview_data)
        )
        conn.commit()
        return jsonify({'message': 'Application created successfully', 'application_id': cursor.lastrowid}), 201
    except Exception as e:
        conn.rollback()
        if is_bad_input(e):
            return jsonify({'error': f'Invalid value: {e.msg}'}), 400
        print(f"Error creating application: {e}")
        return jsonify({'error': 'An error occurred while creating the application'}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/api/applications/<int:application_id>', methods=['GET'])
def get_application(application_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute('SELECT * FROM applications WHERE application_id = %s', (application_id,))
        application = cursor.fetchone()
    finally:
        cursor.close()
        conn.close()
    if application:
        return jsonify(application)
    else:
        return jsonify({'error': 'Application not found'}), 404

@app.route('/api/applications/<int:application_id>', methods=['PUT'])
def update_application(application_id):
    data = request.get_json(silent=True)
    return update_row('applications', 'application_id', application_id, data,
                      ['job_id', 'application_date', 'status', 'resume_version', 'cover_letter_sent', 'interview_data'],
                      json_fields=('interview_data',), label='Application')

@app.route('/api/applications/<int:application_id>', methods=['DELETE'])
def delete_application(application_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('DELETE FROM applications WHERE application_id = %s', (application_id,))
        conn.commit()
        if cursor.rowcount == 0:
            return jsonify({'error': 'Application not found'}), 404
        return jsonify({'message': 'Application deleted successfully'})
    except Exception as e:
        conn.rollback()
        if is_bad_input(e):
            return jsonify({'error': f'Invalid value: {e.msg}'}), 400
        print(f"Error deleting application: {e}")
        return jsonify({'error': 'An error occurred while deleting the application'}), 500
    finally:
        cursor.close()
        conn.close()


#   ----------- contacts routes ----------
@app.route('/api/contacts', methods=['GET'])
def get_contacts():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute('SELECT * FROM contacts')
        contacts = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()
    return jsonify(contacts)

@app.route('/api/contacts', methods=['POST'])
def create_contact():
    data = request.get_json(silent=True)
    if not data or not data.get('company_id') or not data.get('contact_name'):
        return jsonify({'error': 'company_id and contact_name are required'}), 400
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            'INSERT INTO contacts (company_id, contact_name, title, email, phone, linkedin_url, notes) '
            'VALUES (%s, %s, %s, %s, %s, %s, %s)',
            (data.get('company_id'), data.get('contact_name'), data.get('title'),
             data.get('email'), data.get('phone'), data.get('linkedin_url'), data.get('notes'))
        )
        conn.commit()
        return jsonify({'message': 'Contact created successfully', 'contact_id': cursor.lastrowid}), 201
    except Exception as e:
        conn.rollback()
        if is_bad_input(e):
            return jsonify({'error': f'Invalid value: {e.msg}'}), 400
        print(f"Error creating contact: {e}")
        return jsonify({'error': 'An error occurred while creating the contact'}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/api/contacts/<int:contact_id>', methods=['GET'])
def get_contact(contact_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute('SELECT * FROM contacts WHERE contact_id = %s', (contact_id,))
        contact = cursor.fetchone()
    finally:
        cursor.close()
        conn.close()
    if contact:
        return jsonify(contact)
    else:
        return jsonify({'error': 'Contact not found'}), 404

@app.route('/api/contacts/<int:contact_id>', methods=['PUT'])
def update_contact(contact_id):
    data = request.get_json(silent=True)
    return update_row('contacts', 'contact_id', contact_id, data,
                      ['company_id', 'contact_name', 'title', 'email', 'phone', 'linkedin_url', 'notes'],
                      json_fields=(), label='Contact')

@app.route('/api/contacts/<int:contact_id>', methods=['DELETE'])
def delete_contact(contact_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('DELETE FROM contacts WHERE contact_id = %s', (contact_id,))
        conn.commit()
        if cursor.rowcount == 0:
            return jsonify({'error': 'Contact not found'}), 404
        return jsonify({'message': 'Contact deleted successfully'})
    except Exception as e:
        conn.rollback()
        if is_bad_input(e):
            return jsonify({'error': f'Invalid value: {e.msg}'}), 400
        print(f"Error deleting contact: {e}")
        return jsonify({'error': 'An error occurred while deleting the contact'}), 500
    finally:
        cursor.close()
        conn.close()

#   ----------- Dashboard / applications / job match pages -----------
STATUSES = ['Applied', 'Screening', 'Interview', 'Offer', 'Rejected', 'Withdrawn']

@app.route('/dashboard')
def dashboard():
    counts = fetch_all(
        'SELECT (SELECT COUNT(*) FROM companies) AS companies, '
        '(SELECT COUNT(*) FROM jobs) AS jobs, '
        '(SELECT COUNT(*) FROM applications) AS applications, '
        '(SELECT COUNT(*) FROM contacts) AS contacts'
    )[0]
    by_status = {row['status']: row['total'] for row in fetch_all(
        'SELECT status, COUNT(*) AS total FROM applications GROUP BY status')}
    status_counts = [(s, by_status.get(s, 0)) for s in STATUSES]
    recent = fetch_all(
        'SELECT a.application_id, a.application_date, a.status, j.job_title, c.company_name '
        'FROM applications a JOIN jobs j ON a.job_id = j.job_id '
        'JOIN companies c ON j.company_id = c.company_id '
        'ORDER BY a.application_date DESC, a.application_id DESC LIMIT 5'
    )
    return render_template('dashboard.html', counts=counts,
                           status_counts=status_counts, recent=recent)

@app.route('/applications')
def applications():
    rows = fetch_all(
        'SELECT a.*, j.job_title, c.company_name '
        'FROM applications a JOIN jobs j ON a.job_id = j.job_id '
        'JOIN companies c ON j.company_id = c.company_id '
        'ORDER BY a.application_date DESC, a.application_id DESC'
    )
    for row in rows:
        row['interview_data'] = parse_json_column(row['interview_data'])
    return render_template('applications.html', applications=rows, jobs=job_options(),
                           statuses=status_options())

def requirement_list(raw):
    """Turn the jobs.requirements JSON column into a list of lowercase strings.

    Accepts a JSON list (["python", "sql"]) or an object whose values are
    lists/strings ({"skills": ["python"], "nice_to_have": "docker"}).
    """
    if raw is None:
        return []
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode()
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            raw = [raw]
    if isinstance(raw, dict):
        raw = [v for value in raw.values()
               for v in (value if isinstance(value, list) else [value])]
    if not isinstance(raw, list):
        raw = [raw]
    return [str(r).strip().lower() for r in raw if str(r).strip()]

@app.route('/job-match')
def job_match():
    skills_text = request.args.get('skills', '')
    skills = {s.strip().lower() for s in skills_text.split(',') if s.strip()}
    results = []
    if skills:
        for job in fetch_all(
                'SELECT j.job_id, j.job_title, j.requirements, c.company_name '
                'FROM jobs j JOIN companies c ON j.company_id = c.company_id'):
            reqs = requirement_list(job['requirements'])
            if not reqs:
                continue
            matched = [r for r in reqs if r in skills]
            results.append({
                'job': job,
                'matched': matched,
                'missing': [r for r in reqs if r not in skills],
                'total': len(reqs),
                'score': round(100 * len(matched) / len(reqs)),
            })
        # Highest % first; ties broken by more matched skills, then title.
        results.sort(key=lambda r: (-r['score'], -len(r['matched']), r['job']['job_title']))
    return render_template('job_match.html', skills_text=skills_text,
                           searched=bool(skills), results=results)


#   ----------- Detail pages -----------
def job_options():
    return [
        {'value': r['job_id'], 'label': f"{r['job_title']} — {r['company_name']}"}
        for r in fetch_all(
            'SELECT j.job_id, j.job_title, c.company_name FROM jobs j '
            'JOIN companies c ON j.company_id = c.company_id ORDER BY c.company_name, j.job_title'
        )
    ]

def status_options():
    return [{'value': s, 'label': s} for s in STATUSES]

@app.route('/companies/<int:company_id>')
def company_detail(company_id):
    company = fetch_one_or_404('SELECT * FROM companies WHERE company_id = %s', (company_id,))
    company_jobs = fetch_all(
        'SELECT j.*, COUNT(a.application_id) AS application_count FROM jobs j '
        'LEFT JOIN applications a ON a.job_id = j.job_id '
        'WHERE j.company_id = %s GROUP BY j.job_id ORDER BY j.job_title', (company_id,))
    company_contacts = fetch_all(
        'SELECT * FROM contacts WHERE company_id = %s ORDER BY contact_name', (company_id,))
    return render_template('company_detail.html', company=company,
                           jobs=company_jobs, contacts=company_contacts)

@app.route('/jobs/<int:job_id>')
def job_detail(job_id):
    job = fetch_one_or_404(
        'SELECT j.*, c.company_name FROM jobs j '
        'JOIN companies c ON j.company_id = c.company_id WHERE j.job_id = %s', (job_id,))
    job['requirements'] = parse_json_column(job['requirements'])
    job_applications = fetch_all(
        'SELECT * FROM applications WHERE job_id = %s '
        'ORDER BY application_date DESC, application_id DESC', (job_id,))
    return render_template('job_detail.html', job=job, applications=job_applications,
                           companies=company_options())

@app.route('/applications/<int:application_id>')
def application_detail(application_id):
    application = fetch_one_or_404(
        'SELECT a.*, j.job_title, j.job_url, c.company_id, c.company_name '
        'FROM applications a JOIN jobs j ON a.job_id = j.job_id '
        'JOIN companies c ON j.company_id = c.company_id '
        'WHERE a.application_id = %s', (application_id,))
    application['interview_data'] = parse_json_column(application['interview_data'])
    return render_template('application_detail.html', app_row=application,
                           jobs=job_options(), statuses=status_options())

@app.route('/contacts/<int:contact_id>')
def contact_detail(contact_id):
    contact = fetch_one_or_404(
        'SELECT ct.*, c.company_name FROM contacts ct '
        'JOIN companies c ON ct.company_id = c.company_id WHERE ct.contact_id = %s', (contact_id,))
    return render_template('contact_detail.html', contact=contact,
                           companies=company_options())


if __name__ == '__main__':
    app.run(debug=True)
