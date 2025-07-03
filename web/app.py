from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_file
import sqlite3
from datetime import datetime
import hashlib
import os
from functools import wraps
from dotenv import load_dotenv # find_dotenv is no longer strictly needed if we construct the path
import requests  # For sending Telegram messages and downloading files
import io  # For handling file downloads

# Construct the path to the .env file relative to the current script (app.py)
# app.py is in web/, .env is in env/ at project root
dotenv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'env', '.env')

# Load environment variables from the specified .env file
# raise_error_if_not_found=True is used here to ensure the file exists
load_dotenv(dotenv_path, override=True, verbose=True) # Added override=True and verbose=True for debugging

BOT_TOKEN = os.getenv('BOT_TOKEN')  # Get bot token for sending messages/downloading files

app = Flask(__name__)
# Set a strong secret key for production. This is crucial for session security.
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'FALLBACK_SECRET_KEY')

# Admin credentials for initial setup.
ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin123')

def hash_password(password):
    """Hashes a password using SHA256 for secure storage."""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password, hashed):
    """Verifies a plain-text password against a stored hash."""
    return hash_password(password) == hashed

def get_db_connection():
    """Establishes and returns a database connection to jobs_bot.db."""
    # Determine the path to the database file, now located in the 'db' directory
    # It's two levels up from web/app.py, then into the 'db' folder
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'db', 'jobs_bot.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def init_admin_db():
    """Initializes admin-specific database tables and inserts a default admin if none exists."""
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM admins")
    if cursor.fetchone()[0] == 0:
        admin_hash = hash_password(ADMIN_PASSWORD)
        conn.execute('''
            INSERT INTO admins (username, password_hash)
            VALUES (?, ?)
        ''', (ADMIN_USERNAME, admin_hash))
        print(f"Default admin user '{ADMIN_USERNAME}' created with password '{ADMIN_PASSWORD}'. PLEASE CHANGE THIS IN PRODUCTION!")
    conn.commit()
    conn.close()

init_admin_db()

def login_required(f):
    """Decorator to protect routes, redirecting unauthenticated users to the login page."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            flash('Please log in to access this page.', 'info')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    """Redirects to the dashboard if logged in, otherwise to the login page."""
    if 'logged_in' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handles admin login."""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        admin = conn.execute(
            'SELECT * FROM admins WHERE username = ?', (username,)
        ).fetchone()
        conn.close()
        if admin and verify_password(password, admin['password_hash']):
            session['logged_in'] = True
            session['admin_id'] = admin['id']
            session['username'] = admin['username']
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password!', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Logs out the current admin user."""
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    """Displays the admin dashboard with key statistics and recent activities."""
    conn = get_db_connection()
    stats = {
        'total_jobs': conn.execute('SELECT COUNT(*) FROM jobs').fetchone()[0],
        'active_jobs': conn.execute('SELECT COUNT(*) FROM jobs WHERE is_active = 1').fetchone()[0],
        'total_users': conn.execute('SELECT COUNT(*) FROM users').fetchone()[0],
        'total_applications': conn.execute('SELECT COUNT(*) FROM applications').fetchone()[0],
        'pending_applications': conn.execute('SELECT COUNT(*) FROM applications WHERE status = "pending"').fetchone()[0]
    }
    recent_applications = conn.execute('''
        SELECT a.id, u.full_name, u.email, j.title, a.status, a.applied_at
        FROM applications a
        JOIN users u ON a.user_id = u.user_id
        JOIN jobs j ON a.job_id = j.id
        ORDER BY a.applied_at DESC
        LIMIT 10
    ''').fetchall()
    popular_jobs = conn.execute('''
        SELECT j.title, j.location, COUNT(a.id) as application_count
        FROM jobs j
        LEFT JOIN applications a ON j.id = a.job_id
        WHERE j.is_active = 1
        GROUP BY j.id, j.title, j.location
        ORDER BY application_count DESC
        LIMIT 5
    ''').fetchall()
    conn.close()
    return render_template('dashboard.html',
                           stats=stats,
                           recent_applications=recent_applications,
                           popular_jobs=popular_jobs)


# Line 130 (start of jobs function)
@app.route('/jobs')
@login_required
def jobs():
    """Displays a list of all job postings with their application counts and filtering options."""
    conn = get_db_connection()

    # Filtering parameters
    status_filter = request.args.get('status', 'all')
    search_query = request.args.get('search', '').strip()

    query = '''
        SELECT j.*, COUNT(a.id) as application_count
        FROM jobs j
        LEFT JOIN applications a ON j.id = a.job_id
        WHERE 1=1
    '''
    params = []

    if status_filter != 'all':
        query += ' AND j.is_active = ?'
        params.append(1 if status_filter == 'active' else 0)

    if search_query:
        query += ' AND (j.title LIKE ? OR j.description LIKE ? OR j.location LIKE ?)'
        params.extend([f'%{search_query}%', f'%{search_query}%', f'%{search_query}%'])

    query += ' GROUP BY j.id ORDER BY j.created_at DESC'

    jobs_list = conn.execute(query, params).fetchall()
    conn.close()

    return render_template('jobs.html', jobs=jobs_list, status_filter=status_filter, search_query=search_query)

@app.route('/jobs/add', methods=['GET', 'POST'])
@login_required
def add_job():
    """Handles adding new job postings."""
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        requirements = request.form['requirements']
        location = request.form['location']
        salary = request.form['salary']
        if not title or not description:
            flash('Job Title and Description are required!', 'error')
            return render_template('add_job.html')
        conn = get_db_connection()
        conn.execute('''
            INSERT INTO jobs (title, description, requirements, location, salary)
            VALUES (?, ?, ?, ?, ?)
        ''', (title, description, requirements, location, salary))
        conn.commit()
        conn.close()
        flash('Job posted successfully!', 'success')
        return redirect(url_for('jobs'))
    return render_template('add_job.html')

@app.route('/jobs/edit/<int:job_id>', methods=['GET', 'POST'])
@login_required
def edit_job(job_id):
    """Handles editing existing job postings."""
    conn = get_db_connection()
    job = conn.execute('SELECT * FROM jobs WHERE id = ?', (job_id,)).fetchone()
    if not job:
        flash('Job not found!', 'error')
        conn.close()
        return redirect(url_for('jobs'))
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        requirements = request.form['requirements']
        location = request.form['location']
        salary = request.form['salary']
        is_active = 1 if 'is_active' in request.form else 0
        if not title or not description:
            flash('Job Title and Description are required!', 'error')
            conn.close()
            return render_template('edit_job.html', job=job)
        conn.execute('''
            UPDATE jobs
            SET title=?, description=?, requirements=?, location=?, salary=?, is_active=?
            WHERE id=?
        ''', (title, description, requirements, location, salary, is_active, job_id))
        conn.commit()
        conn.close()
        flash('Job updated successfully!', 'success')
        return redirect(url_for('jobs'))
    conn.close()
    return render_template('edit_job.html', job=job)

@app.route('/jobs/delete/<int:job_id>')
@login_required
def delete_job(job_id):
    """Deletes a job posting or deactivates it if it has applications."""
    conn = get_db_connection()
    applications_count = conn.execute('SELECT COUNT(*) FROM applications WHERE job_id = ?', (job_id,)).fetchone()[0]
    if applications_count > 0:
        conn.execute('UPDATE jobs SET is_active = 0 WHERE id = ?', (job_id,))
        flash('Job has existing applications and was therefore deactivated instead of deleted. You can reactivate it from the edit page.', 'warning')
    else:
        conn.execute('DELETE FROM jobs WHERE id = ?', (job_id,))
        flash('Job deleted successfully!', 'success')
    conn.commit()
    conn.close()
    return redirect(url_for('jobs'))


# Line 209 (start of applications function)
@app.route('/applications')
@login_required
def applications():
    """Displays a list of all job applications with filtering options."""
    status_filter = request.args.get('status', 'all')
    job_filter = request.args.get('job', 'all')
    search_query = request.args.get('search', '').strip()  # New search query

    conn = get_db_connection()

    query = '''
        SELECT a.*, u.full_name, u.email, u.phone, u.username, j.title as job_title, j.location
        FROM applications a
        JOIN users u ON a.user_id = u.user_id
        JOIN jobs j ON a.job_id = j.id
        WHERE 1=1
    '''
    params = []

    if status_filter != 'all':
        query += ' AND a.status = ?'
        params.append(status_filter)

    if job_filter != 'all':
        query += ' AND a.job_id = ?'
        params.append(int(job_filter))

    # New: Search by applicant name, email, or Telegram username
    if search_query:
        query += ' AND (u.full_name LIKE ? OR u.email LIKE ? OR u.username LIKE ?)'
        params.extend([f'%{search_query}%', f'%{search_query}%', f'%{search_query}%'])

    query += ' ORDER BY a.applied_at DESC'

    applications_list = conn.execute(query, params).fetchall()

    jobs_list = conn.execute('SELECT id, title FROM jobs ORDER BY title').fetchall()
    conn.close()

    return render_template('applications.html',
                           applications=applications_list,
                           jobs=jobs_list,
                           status_filter=status_filter,
                           job_filter=job_filter,
                           search_query=search_query)  # Pass search_query to template

@app.route('/applications/view/<int:app_id>')
@login_required
def view_application(app_id):
    """Displays detailed information about a specific job application."""
    conn = get_db_connection()
    application = conn.execute('''
        SELECT a.*, u.*, j.title as job_title, j.description as job_description,
               j.requirements as job_requirements, j.location as job_location, j.salary as job_salary
        FROM applications a
        JOIN users u ON a.user_id = u.user_id
        JOIN jobs j ON a.job_id = j.id
        WHERE a.id = ?
    ''', (app_id,)).fetchone()
    conn.close()
    if not application:
        flash('Application not found!', 'error')
        return redirect(url_for('applications'))
    return render_template('view_application.html', app=application)

@app.route('/applications/update_status/<int:app_id>', methods=['POST'])
@login_required
def update_application_status(app_id):
    """Updates the status of a specific job application."""
    new_status = request.form['status']
    if new_status not in ['pending', 'accepted', 'rejected', 'interviewed']:
        flash('Invalid status!', 'error')
        return redirect(url_for('view_application', app_id=app_id))
    conn = get_db_connection()
    conn.execute('UPDATE applications SET status = ? WHERE id = ?', (new_status, app_id))
    conn.commit()
    conn.close()
    flash(f'Application status updated to {new_status.title()}!', 'success')
    return redirect(url_for('view_application', app_id=app_id))


# (start of users function)
@app.route('/users')
@login_required
def users():
    """Displays a list of all registered users with their application counts and filtering options."""
    conn = get_db_connection()
    search_query = request.args.get('search', '').strip()  # New search query

    query = '''
        SELECT u.*, COUNT(a.id) as application_count
        FROM users u
        LEFT JOIN applications a ON u.user_id = a.user_id
        WHERE 1=1
    '''
    params = []

    # New: Search by user full name, username, or email
    if search_query:
        query += ' AND (u.full_name LIKE ? OR u.username LIKE ? OR u.email LIKE ?)'
        params.extend([f'%{search_query}%', f'%{search_query}%', f'%{search_query}%'])

    query += ' GROUP BY u.user_id ORDER BY u.created_at DESC'

    users_list = conn.execute(query, params).fetchall()
    conn.close()

    return render_template('users.html', users=users_list, search_query=search_query)  # Pass search_query

@app.route('/users/view/<int:user_id>')
@login_required
def view_user(user_id):
    """Displays detailed information about a specific user and their applications."""
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE user_id = ?', (user_id,)).fetchone()
    if not user:
        flash('User not found!', 'error')
        return redirect(url_for('users'))
    user_applications = conn.execute('''
        SELECT a.*, j.title, j.location
        FROM applications a
        JOIN jobs j ON a.job_id = j.id
        WHERE a.user_id = ?
        ORDER BY a.applied_at DESC
    ''', (user_id,)).fetchall()
    conn.close()
    return render_template('view_user.html', user=user, applications=user_applications)

@app.route('/api/stats')
@login_required
def api_stats():
    """API endpoint to provide dashboard statistics in JSON format."""
    conn = get_db_connection()
    stats = {
        'total_jobs': conn.execute('SELECT COUNT(*) FROM jobs').fetchone()[0],
        'active_jobs': conn.execute('SELECT COUNT(*) FROM jobs WHERE is_active = 1').fetchone()[0],
        'total_users': conn.execute('SELECT COUNT(*) FROM users').fetchone()[0],
        'total_applications': conn.execute('SELECT COUNT(*) FROM applications').fetchone()[0],
        'pending_applications': conn.execute('SELECT COUNT(*) FROM applications WHERE status = "pending"').fetchone()[0]
    }
    conn.close()
    return jsonify(stats)


# Line 367 (new function)
@app.route('/send_telegram_message', methods=['POST'])
@login_required
def send_telegram_message():
    """Sends a message to a specific Telegram user via the bot."""
    user_id = request.form.get('user_id')
    message_text = request.form.get('message_text')

    if not user_id or not message_text:
        flash('User ID and message text are required.', 'error')
        return redirect(request.referrer or url_for('dashboard'))

    if not BOT_TOKEN:
        flash('Telegram BOT_TOKEN is not configured in .env!', 'error')
        return redirect(request.referrer or url_for('dashboard'))

    telegram_api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': user_id,
        'text': message_text,
        'parse_mode': 'Markdown'  # Allow markdown in messages
    }

    try:
        response = requests.post(telegram_api_url, json=payload)
        response.raise_for_status()  # Raise an exception for HTTP errors
        flash(f'Message sent to Telegram user {user_id} successfully!', 'success')
    except requests.exceptions.RequestException as e:
        flash(f'Failed to send message to Telegram user {user_id}: {e}', 'error')
    except Exception as e:
        flash(f'An unexpected error occurred: {e}', 'error')

    return redirect(request.referrer or url_for('dashboard'))  # Redirect back to the page they came from


# Line 400 (new function)
@app.route('/download_resume/<file_id>')
@login_required
def download_resume(file_id):
    """Downloads a resume file from Telegram using its file_id."""
    if not BOT_TOKEN:
        flash('Telegram BOT_TOKEN is not configured in .env!', 'error')
        return redirect(request.referrer or url_for('dashboard'))

    # Get file path from Telegram
    get_file_url = f"https://api.telegram.org/bot{BOT_TOKEN}/getFile?file_id={file_id}"
    try:
        response = requests.get(get_file_url)
        response.raise_for_status()
        file_info = response.json().get('result')

        if not file_info:
            flash('Could not get file information from Telegram.', 'error')
            return redirect(request.referrer or url_for('dashboard'))

        file_path = file_info.get('file_path')
        if not file_path:
            flash('File path not found in Telegram response.', 'error')
            return redirect(request.referrer or url_for('dashboard'))

        download_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"

        # Download the file content
        file_content_response = requests.get(download_url, stream=True)
        file_content_response.raise_for_status()

        # Determine filename (Telegram often provides it in file_path or original upload)
        # We can try to extract it from file_path or use a generic name
        filename = os.path.basename(file_path)
        if not filename:
            filename = f"resume_{file_id}.bin"  # Fallback generic name

        # Use io.BytesIO to create an in-memory file for send_file
        return send_file(
            io.BytesIO(file_content_response.content),
            mimetype=file_info.get('mime_type', 'application/octet-stream'),
            as_attachment=True,
            download_name=filename
        )

    except requests.exceptions.RequestException as e:
        flash(f'Failed to download resume from Telegram: {e}', 'error')
    except Exception as e:
        flash(f'An unexpected error occurred during resume download: {e}', 'error')

    return redirect(request.referrer or url_for('dashboard'))

# Line 452 (new function)
@app.template_filter('nl2br')
def nl2br_filter(s):
    """Converts newline characters in a string to HTML <br> tags."""
    return s.replace('\n', '<br>') if s else ''

@app.template_filter('datetime')
def datetime_filter(value):
    """Formats a datetime string for display (e.g., 'July 03, 2025 at 12:00 PM')."""
    if value:
        return datetime.strptime(value, '%Y-%m-%d %H:%M:%S').strftime('%B %d, %Y at %I:%M %p')
    return ''

@app.template_filter('date')
def date_filter(value):
    """Formats a datetime string for display (e.g., 'July 03, 2025')."""
    if value:
        return datetime.strptime(value, '%Y-%m-%d %H:%M:%S').strftime('%B %d, %Y')
    return ''

@app.template_filter('nl2br')
def nl2br_filter(s):
    """Converts newline characters in a string to HTML <br> tags."""
    return s.replace('\n', '<br>') if s else ''

if __name__ == '__main__':
    debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() in ('true', '1', 't')
    app.run(debug=debug_mode, host='0.0.0.0', port=5000)