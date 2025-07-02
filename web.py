from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import sqlite3
from datetime import datetime
import hashlib
import os
from functools import wraps

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this-in-production'

# Admin credentials (in production, use proper authentication)
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"  # Change this in production


def hash_password(password):
    """Hash password using SHA256"""
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(password, hashed):
    """Verify password against hash"""
    return hash_password(password) == hashed


def login_required(f):
    """Decorator to require login for protected routes"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)

    return decorated_function


def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect('jobs_bot.db')
    conn.row_factory = sqlite3.Row
    return conn


def init_admin_db():
    """Initialize admin-specific database tables"""
    conn = get_db_connection()

    # Create admin table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Insert default admin if not exists
    admin_hash = hash_password(ADMIN_PASSWORD)
    conn.execute('''
        INSERT OR IGNORE INTO admins (username, password_hash) 
        VALUES (?, ?)
    ''', (ADMIN_USERNAME, admin_hash))

    conn.commit()
    conn.close()


# Initialize database on startup
init_admin_db()


@app.route('/')
def index():
    """Home page - redirect to dashboard if logged in, else show login"""
    if 'logged_in' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Admin login page"""
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
    """Logout admin"""
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))


@app.route('/dashboard')
@login_required
def dashboard():
    """Admin dashboard with statistics"""
    conn = get_db_connection()

    # Get statistics
    stats = {
        'total_jobs': conn.execute('SELECT COUNT(*) FROM jobs').fetchone()[0],
        'active_jobs': conn.execute('SELECT COUNT(*) FROM jobs WHERE is_active = 1').fetchone()[0],
        'total_users': conn.execute('SELECT COUNT(*) FROM users').fetchone()[0],
        'total_applications': conn.execute('SELECT COUNT(*) FROM applications').fetchone()[0],
        'pending_applications': conn.execute('SELECT COUNT(*) FROM applications WHERE status = "pending"').fetchone()[0]
    }

    # Get recent applications
    recent_applications = conn.execute('''
        SELECT a.id, u.full_name, u.email, j.title, a.status, a.applied_at
        FROM applications a
        JOIN users u ON a.user_id = u.user_id
        JOIN jobs j ON a.job_id = j.id
        ORDER BY a.applied_at DESC
        LIMIT 10
    ''').fetchall()

    # Get popular jobs
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


@app.route('/jobs')
@login_required
def jobs():
    """View all jobs"""
    conn = get_db_connection()
    jobs = conn.execute('''
        SELECT j.*, COUNT(a.id) as application_count
        FROM jobs j
        LEFT JOIN applications a ON j.id = a.job_id
        GROUP BY j.id
        ORDER BY j.created_at DESC
    ''').fetchall()
    conn.close()

    return render_template('jobs.html', jobs=jobs)


@app.route('/jobs/add', methods=['GET', 'POST'])
@login_required
def add_job():
    """Add new job posting"""
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        requirements = request.form['requirements']
        location = request.form['location']
        salary = request.form['salary']

        if not title or not description:
            flash('Title and description are required!', 'error')
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
    """Edit existing job posting"""
    conn = get_db_connection()
    job = conn.execute('SELECT * FROM jobs WHERE id = ?', (job_id,)).fetchone()

    if not job:
        flash('Job not found!', 'error')
        return redirect(url_for('jobs'))

    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        requirements = request.form['requirements']
        location = request.form['location']
        salary = request.form['salary']
        is_active = 1 if 'is_active' in request.form else 0

        if not title or not description:
            flash('Title and description are required!', 'error')
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
    """Delete job posting"""
    conn = get_db_connection()

    # Check if job has applications
    applications = conn.execute('SELECT COUNT(*) FROM applications WHERE job_id = ?', (job_id,)).fetchone()[0]

    if applications > 0:
        # Don't delete, just deactivate
        conn.execute('UPDATE jobs SET is_active = 0 WHERE id = ?', (job_id,))
        flash('Job deactivated (has applications). You can reactivate it later.', 'warning')
    else:
        # Safe to delete
        conn.execute('DELETE FROM jobs WHERE id = ?', (job_id,))
        flash('Job deleted successfully!', 'success')

    conn.commit()
    conn.close()

    return redirect(url_for('jobs'))


@app.route('/applications')
@login_required
def applications():
    """View all applications"""
    status_filter = request.args.get('status', 'all')
    job_filter = request.args.get('job', 'all')

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

    query += ' ORDER BY a.applied_at DESC'

    applications = conn.execute(query, params).fetchall()

    # Get jobs for filter dropdown
    jobs = conn.execute('SELECT id, title FROM jobs ORDER BY title').fetchall()

    conn.close()

    return render_template('applications.html',
                           applications=applications,
                           jobs=jobs,
                           status_filter=status_filter,
                           job_filter=job_filter)


@app.route('/applications/view/<int:app_id>')
@login_required
def view_application(app_id):
    """View detailed application"""
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
    """Update application status"""
    new_status = request.form['status']

    if new_status not in ['pending', 'accepted', 'rejected', 'interviewed']:
        flash('Invalid status!', 'error')
        return redirect(url_for('applications'))

    conn = get_db_connection()
    conn.execute('UPDATE applications SET status = ? WHERE id = ?', (new_status, app_id))
    conn.commit()
    conn.close()

    flash(f'Application status updated to {new_status}!', 'success')
    return redirect(url_for('view_application', app_id=app_id))


@app.route('/users')
@login_required
def users():
    """View all users"""
    conn = get_db_connection()

    users = conn.execute('''
        SELECT u.*, COUNT(a.id) as application_count
        FROM users u
        LEFT JOIN applications a ON u.user_id = a.user_id
        GROUP BY u.user_id
        ORDER BY u.created_at DESC
    ''').fetchall()

    conn.close()

    return render_template('users.html', users=users)


@app.route('/users/view/<int:user_id>')
@login_required
def view_user(user_id):
    """View detailed user profile"""
    conn = get_db_connection()

    user = conn.execute('SELECT * FROM users WHERE user_id = ?', (user_id,)).fetchone()

    if not user:
        flash('User not found!', 'error')
        return redirect(url_for('users'))

    # Get user's applications
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
    """API endpoint for dashboard statistics"""
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


# Template filters
@app.template_filter('datetime')
def datetime_filter(value):
    """Format datetime for display"""
    if value:
        return datetime.strptime(value, '%Y-%m-%d %H:%M:%S').strftime('%B %d, %Y at %I:%M %p')
    return ''


@app.template_filter('date')
def date_filter(value):
    """Format date for display"""
    if value:
        return datetime.strptime(value, '%Y-%m-%d %H:%M:%S').strftime('%B %d, %Y')
    return ''


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)