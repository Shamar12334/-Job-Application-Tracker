"""Sample data for the job tracker.

Run with:   flask --app app seed-db          (only if the database is empty)
            flask --app app seed-db --reset  (delete everything first, then seed)

All companies and people are made up; websites and emails use example.com.
"""
import json

# (company_name, industry, website, city, state, notes)
COMPANIES = [
    ('Brightpath Analytics', 'Data & Analytics', 'https://brightpath.example.com', 'Austin', 'TX',
     'Mid-size analytics firm. Strong mentorship program for junior engineers.'),
    ('Northwind Health', 'Healthcare', 'https://northwind-health.example.com', 'Boston', 'MA',
     'Patient portal team is growing. Hybrid, 2 days in office.'),
    ('Cobalt Payments', 'Fintech', 'https://cobaltpay.example.com', 'New York', 'NY',
     'Fast-paced. Interview process is 4 rounds including a take-home.'),
    ('Greenline Logistics', 'Logistics', 'https://greenline.example.com', 'Atlanta', 'GA', None),
    ('Pixel Harbor Studios', 'Gaming', 'https://pixelharbor.example.com', 'Seattle', 'WA',
     'Met their recruiter at the career fair.'),
    ('Summit Cloud Systems', 'Cloud Infrastructure', 'https://summitcloud.example.com', 'Denver', 'CO',
     'Fully remote option available.'),
]

# (company index, job_title, job_type, salary_min, salary_max, url slug, date_posted, requirements)
JOBS = [
    (0, 'Junior Data Engineer', 'Full-time', 72000, 90000, 'jde-101', '2026-10-02',
     ['Python', 'SQL', 'Airflow', 'Git']),
    (0, 'Data Analyst Intern', 'Internship', 22, 28, 'intern-da', '2026-10-20',
     ['SQL', 'Excel', 'Tableau']),
    (1, 'Backend Developer', 'Full-time', 85000, 110000, 'backend-dev', '2026-09-28',
     ['Python', 'Flask', 'MySQL', 'REST APIs', 'Docker']),
    (1, 'QA Automation Engineer', 'Contract', 60, 75, 'qa-auto', '2026-10-15',
     ['Python', 'Selenium', 'CI/CD']),
    (2, 'Software Engineer I', 'Full-time', 105000, 130000, 'swe-1', '2026-10-05',
     ['Java', 'SQL', 'Spring', 'Git']),
    (2, 'Full Stack Developer', 'Full-time', 110000, 140000, 'fullstack', '2026-11-01',
     ['JavaScript', 'React', 'Python', 'SQL', 'Docker']),
    (3, 'IT Support Specialist', 'Part-time', 25, 32, 'it-support', '2026-10-10',
     ['Windows', 'Networking', 'Customer Service']),
    (4, 'Gameplay Programmer', 'Full-time', 80000, 105000, 'gameplay', '2026-10-25',
     ['C++', 'Unity', 'C#', 'Git']),
    (5, 'Cloud Support Engineer', 'Full-time', 78000, 98000, 'cloud-support', '2026-10-12',
     ['Linux', 'AWS', 'Python', 'Networking']),
    (5, 'DevOps Intern', 'Internship', 25, 30, 'devops-intern', '2026-11-05',
     ['Linux', 'Docker', 'Git', 'Python']),
]

# (job index, application_date, status, resume_version, cover_letter_sent, interview_data)
APPLICATIONS = [
    (0, '2026-10-06', 'Interview', 'v3-data', True,
     {'rounds': [{'round': 1, 'type': 'Phone screen', 'date': '2026-10-14', 'notes': 'Went well, asked about SQL joins'},
                 {'round': 2, 'type': 'Technical', 'date': '2026-11-20'}]}),
    (2, '2026-10-01', 'Offer', 'v3-backend', True,
     {'rounds': [{'round': 1, 'type': 'Phone screen', 'date': '2026-10-08'},
                 {'round': 2, 'type': 'Technical', 'date': '2026-10-17'},
                 {'round': 3, 'type': 'Final', 'date': '2026-10-29'}],
      'offer': {'salary': 98000, 'deadline': '2026-11-25'}}),
    (3, '2026-10-18', 'Rejected', 'v2', False, None),
    (4, '2026-10-09', 'Screening', 'v3-backend', True,
     {'rounds': [{'round': 1, 'type': 'Recruiter call', 'date': '2026-11-19'}]}),
    (5, '2026-11-03', 'Applied', 'v3-backend', True, None),
    (7, '2026-10-27', 'Applied', 'v2-games', False, None),
    (8, '2026-10-14', 'Withdrawn', 'v3-backend', False,
     {'notes': 'Withdrew after accepting interview elsewhere'}),
    (9, '2026-11-07', 'Applied', 'v3-backend', True, None),
]

# (company index, contact_name, title, email local part, phone, linkedin slug, notes)
CONTACTS = [
    (0, 'Maya Patel', 'Technical Recruiter', 'maya.patel', '512-555-0142', 'maya-patel-demo',
     'Very responsive. Prefers email.'),
    (1, 'Jordan Lee', 'Engineering Manager', 'jordan.lee', '617-555-0198', 'jordan-lee-demo',
     'Hiring manager for the backend role. Ran the final interview.'),
    (1, 'Alex Rivera', 'HR Coordinator', 'alex.rivera', None, None, 'Sent the offer letter.'),
    (2, 'Sam Okafor', 'Talent Acquisition', 'sam.okafor', '212-555-0110', 'sam-okafor-demo', None),
    (4, 'Riley Chen', 'Campus Recruiter', 'riley.chen', None, 'riley-chen-demo',
     'Met at the fall career fair. Follow up in December.'),
    (5, 'Taylor Brooks', 'Senior Cloud Engineer', 'taylor.brooks', None, 'taylor-brooks-demo',
     'Alumni connection. Offered to refer me.'),
]


def seed(conn, reset=False):
    """Insert the sample data. Returns a dict of row counts inserted."""
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT COUNT(*) FROM companies')
        if cursor.fetchone()[0] and not reset:
            raise RuntimeError('Database already has data. Use --reset to wipe it and reseed.')
        if reset:
            # Children first; ON DELETE CASCADE would also handle it.
            for table in ('applications', 'contacts', 'jobs', 'companies'):
                cursor.execute(f'DELETE FROM {table}')

        company_ids = []
        for name, industry, website, city, state, notes in COMPANIES:
            cursor.execute(
                'INSERT INTO companies (company_name, industry, website, city, state, notes) '
                'VALUES (%s, %s, %s, %s, %s, %s)',
                (name, industry, website, city, state, notes))
            company_ids.append(cursor.lastrowid)

        job_ids = []
        for ci, title, job_type, smin, smax, slug, posted, reqs in JOBS:
            url = f"{COMPANIES[ci][2]}/careers/{slug}"
            cursor.execute(
                'INSERT INTO jobs (company_id, job_title, job_type, salary_min, salary_max, job_url, date_posted, requirements) '
                'VALUES (%s, %s, %s, %s, %s, %s, %s, %s)',
                (company_ids[ci], title, job_type, smin, smax, url, posted, json.dumps(reqs)))
            job_ids.append(cursor.lastrowid)

        for ji, date, status, resume, cover, interview in APPLICATIONS:
            cursor.execute(
                'INSERT INTO applications (job_id, application_date, status, resume_version, cover_letter_sent, interview_data) '
                'VALUES (%s, %s, %s, %s, %s, %s)',
                (job_ids[ji], date, status, resume, cover,
                 json.dumps(interview) if interview is not None else None))

        for ci, name, title, email, phone, linkedin, notes in CONTACTS:
            cursor.execute(
                'INSERT INTO contacts (company_id, contact_name, title, email, phone, linkedin_url, notes) '
                'VALUES (%s, %s, %s, %s, %s, %s, %s)',
                (company_ids[ci], name, title, f'{email}@example.com', phone,
                 f'https://www.linkedin.com/in/{linkedin}' if linkedin else None, notes))

        conn.commit()
        return {'companies': len(COMPANIES), 'jobs': len(JOBS),
                'applications': len(APPLICATIONS), 'contacts': len(CONTACTS)}
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
