# Telegram Jobs Bot & Admin Portal

This project provides a Telegram bot for job seekers to manage their profiles, browse jobs, and apply, coupled with a Flask-based web administration portal for recruiters/admins to manage job postings, view applications, and communicate with users.

## Table of Contents
1. [Overview](#overview)
2. [Features Implemented](#features-implemented)
3. [Features Not Implemented (and Why)](#features-not-implemented-and-why)
4. [Project Structure](#project-structure)
5. [Setup Instructions](#setup-instructions)
    * [Prerequisites](#prerequisites)
    * [Environment Variables (.env)](#environment-variables-env)
    * [Install Dependencies](#install-dependencies)
    * [Database Setup](#database-setup)
6. [Running the Applications](#running-the-applications)
    * [Run Telegram Bot](#run-telegram-bot)
    * [Run Flask Web Portal](#run-flask-web-portal)
7. [Usage Guide](#usage-guide)
    * [Telegram Bot Usage (Job Seekers)](#telegram-bot-usage-job-seekers)
    * [Web Portal Usage (Admins)](#web-portal-usage-admins)
8. [Security Considerations](#security-considerations)
9. [Troubleshooting](#troubleshooting)

## 1. Overview

This system is designed to streamline the job application process for job seekers through a Telegram bot and provide a robust management interface for administrators.

**Key Components:**
* **Telegram Bot (`tg_bot/bot.py`):** Allows users to create profiles, browse active job listings, apply with pre-filled information, and track application status. Supports resume file uploads.
* **Flask Web Portal (`web/app.py`):** A secure web interface for administrators to post/manage jobs, view detailed applications, review user profiles, and send direct messages to Telegram users.
* **SQLite Database (`db/jobs_bot.db`):** A single database file shared by both the bot and the web portal for data persistence.

## 2. Features Implemented

Here's a detailed list of features that have been implemented in this project:

### Telegram Bot Features:
* **User Profile Management:**
    * Users can create and update their professional profiles (full name, email, phone, experience, skills, resume text).
    * **Email Validation:** Basic regex validation for email addresses during profile creation.
    * **Resume File Upload:** Users can upload their resume as a document (PDF, DOCX, etc.) during profile creation. The bot stores the Telegram `file_id`.
    * **Resume Forwarding to Admin Group:** Uploaded resume files are automatically forwarded to a configured Telegram admin group/channel for easy access by recruiters.
* **Job Browse & Application:**
    * Users can view active job listings via an inline keyboard menu.
    * One-click application using their saved profile data.
    * **Unique Application ID:** Each application is assigned a short, unique public ID (e.g., `A1B2C3D4`) which is displayed to the user upon successful application.
* **Application Tracking:** Users can view a list of their submitted applications with their current status and unique application ID.
* **Help & Navigation:** Clear menu buttons and a `/help` command for guidance.

### Web Portal Features:
* **Admin Authentication:** Secure login for administrators to access the portal.
    * Credentials managed via `.env` for security.
* **Job Management:**
    * Admins can post new job roles with detailed descriptions, requirements, location, and salary.
    * Admins can edit existing job postings.
    * Jobs can be marked as active/inactive.
    * **Job Deactivation/Deletion Logic:** If a job has existing applications, it is deactivated instead of deleted to preserve historical application data.
    * **Job Filtering:** Filter jobs by active/inactive status and search by title, description, or location.
* **Application Management:**
    * View a list of all job applications.
    * **Application Filtering:** Filter applications by status (pending, accepted, rejected, interviewed) and by specific job. Also, search applicants by name, email, or Telegram username.
    * View detailed application information, including applicant profile and job details.
    * Update application status (pending, accepted, rejected, interviewed).
    * **Direct Contact Buttons:** "Send Email" and "Call Phone" buttons on the "View Application" page to contact applicants directly.
    * **Download Resume:** Direct download link for uploaded resume files from Telegram, accessible from the web portal.
* **User Management:**
    * View a list of all registered Telegram users.
    * **User Filtering:** Search users by full name, Telegram username, or email.
    * View detailed user profiles, including their submitted applications.
    * **Direct Telegram Messaging:** A modal popup on both "View Application" and "View User" pages allows admins to send direct Telegram messages to users via the bot.
* **Dashboard:** Provides an overview of key statistics (total jobs, active jobs, total users, total applications, pending applications, recent applications, popular jobs).
* **Environment Variable Integration:** All sensitive keys and configurations (Flask secret key, admin credentials, bot token, admin group ID, debug mode) are loaded from a `.env` file.

## 3. Features Not Implemented (and Why)

The following features were discussed but not implemented in this iteration due to their complexity and scope, which would require significant architectural changes:

* **Custom User Info Definition (without code changes):**
    * **Why not implemented:** This would require dynamic form generation, a flexible database schema (e.g., EAV model or JSON fields), and bot logic capable of interpreting and validating user input based on a runtime-defined schema. This goes beyond the scope of a basic bot and web portal.
* **Selective Profile Updates (Bot):**
    * **Why not implemented:** Allowing users to update only specific fields (e.g., just their email) without re-entering all information requires a more complex, non-linear conversation flow within the Telegram bot. The current implementation uses a sequential conversation handler.

## 4. Project Structure

```

project\_root/
├── tg\_bot/
│   └── bot.py                  \# Telegram bot application logic
├── web/
│   ├── app.py                  \# Flask web portal application logic
│   └── templates/              \# Jinja2 HTML templates for the web portal
│       ├── base.html
│       ├── login.html
│       ├── dashboard.html
│       ├── jobs.html
│       ├── add\_job.html
│       ├── edit\_job.html
│       ├── applications.html
│       ├── view\_application.html
│       ├── users.html
│       └── view\_user.html
├── env/
│   ├── .env                    \# Environment variables (secrets, config) - created from .env.sample
│   └── .env.sample             \# Template for .env file
├── db/
│   └── jobs\_bot.db             \# SQLite database file (created automatically)
├── docs/                       \# All documentation files are now here
│   ├── README.md               \# This documentation file
│   └── docs.md                 \# Original documentation provided by the user
├── .gitignore                  \# Specifies files/directories to ignore in Git
└── requirements.txt            \# Python package dependencies

````

## 5. Setup Instructions

### Prerequisites
* **Python 3.8+**: Ensure Python is installed on your system.
* **pip**: Python's package installer (usually comes with Python).

### Environment Variables (.env)
1.  **Create `.env` file from sample**: In the `project_root/env/` directory, **copy the `.env.sample` file and rename the copy to `.env`**.
2.  **Populate `.env`**: Open the newly created `.env` file and fill in the placeholder values. **Replace placeholder values with your actual secrets and configurations.**

    ```
    # web portal config
    FLASK_SECRET_KEY='your_very_strong_and_unique_secret_key_here' # generate using this command `openssl rand -hex 32`
    FALLBACK_SECRET_KEY='' # backup secret key (optional, can be left empty)
    ADMIN_USERNAME='' # admin username for web portal (e.g., 'admin')
    ADMIN_PASSWORD='' # admin pass for web portal (e.g., 'admin123')
    FLASK_DEBUG='True' # Set to 'True' for development, 'False' for production

    # bot config
    BOT_TOKEN='' # Paste your actual token from BotFather here
    TELEGRAM_ADMIN_GROUP_ID='' # telegram group id for resume forwarding (e.g., '-1234567890123')
    ```

3.  **Generate `FLASK_SECRET_KEY`**:
    * Open your terminal/command prompt.
    * Run `python -c "import secrets; print(secrets.token_hex(32))"`
    * Copy the generated 64-character hexadecimal string and paste it as the `FLASK_SECRET_KEY` value in your `.env` file. (Alternatively, `openssl rand -hex 32` works too).

4.  **Get `BOT_TOKEN`**:
    * Message `@BotFather` on Telegram.
    * Send `/newbot` and follow the instructions to create your bot.
    * BotFather will provide you with an API token. Copy this token and paste it as the `BOT_TOKEN` value in your `.env` file.

5.  **Get `TELEGRAM_ADMIN_GROUP_ID`**:
    * Create a **private Telegram group**.
    * Add your newly created bot to this group.
    * Send any message to the group (e.g., "Hello").
    * In your web browser, go to `https://api.telegram.org/botYOUR_BOT_TOKEN/getUpdates` (replace `YOUR_BOT_TOKEN` with your bot's actual token).
    * Look for the `chat` object in the JSON response. The `id` field within this `chat` object is your `TELEGRAM_ADMIN_GROUP_ID`. It will be a negative number (e.g., `-1001234567890`). Copy this ID and paste it into your `.env` file.

### Install Dependencies
1.  Navigate to your `project_root` directory in your terminal:
    ```bash
    cd path/to/your/project_root
    ```
2.  Install the required Python packages:
    ```bash
    pip install -r requirements.txt
    ```

### Database Setup
The `jobs_bot.db` file will be automatically created in the `project_root/db/` directory when either the bot or the web portal is run for the first time.

**Important:** If you have run the project before and are updating from an older version, the database schema might be outdated.
* **For development (recommended):** Delete the `jobs_bot.db` file from `project_root/db/`. It will be recreated with the new schema and sample data on the next run. (You will lose old user/application data).
* **For production (if retaining data):** You would need to perform a database migration using `ALTER TABLE` statements to add the new columns (`public_application_id` to `applications` and `resume_file_id` to `users`). This is outside the scope of this `README`.

## 6. Running the Applications

You will need two separate terminal windows/tabs to run both the bot and the web portal concurrently.

### Run Telegram Bot
1.  Open a new terminal.
2.  Navigate to the `tg_bot` directory:
    ```bash
    cd path/to/your/project_root/tg_bot
    ```
3.  Run the bot:
    ```bash
    python bot.py
    ```
    You should see `🤖 Jobs Bot is starting...` in your terminal. Keep this terminal open.

### Run Flask Web Portal
1.  Open *another* new terminal.
2.  Navigate to the `web` directory:
    ```bash
    cd path/to/your/project_root/web
    ```
3.  Run the Flask app:
    ```bash
    python app.py
    ```
    You should see output indicating that the Flask development server is running, typically on `http://127.0.0.1:5000/`. Keep this terminal open.

## 7. Usage Guide

### Telegram Bot Usage (Job Seekers)
1.  **Start the Bot**: Go to Telegram, search for your bot's username, and send the `/start` command.
2.  **Create/Update Profile**: Click "📝 Create/Update Profile". Follow the prompts to enter your details. You can send your resume as text or upload a document (PDF, DOCX, etc.) at the "Resume" step.
3.  **View Jobs**: Click "💼 View Jobs" to see available job positions. Click on any job to view details.
4.  **Apply for Job**: On a job details page, if you have a profile, click "✅ Apply Now". You will receive a unique Application ID and status.
5.  **My Applications**: Click "📋 My Applications" to see a list of all your submitted applications with their status and Application IDs.
6.  **Help**: Click "ℹ️ Help" or send `/help` for bot usage instructions.

### Web Portal Usage (Admins)
1.  **Access Portal**: Open your web browser and go to `http://127.0.0.1:5000/`.
2.  **Login**: Use the admin credentials configured in your `.env` file (default: `admin` / `admin123`).
3.  **Dashboard**: View key statistics, recent applications, and popular jobs.
4.  **Manage Jobs**:
    * **View Jobs**: See all job postings. Use the filters to search by title/description/location or status (active/inactive).
    * **Add New Job**: Click "Add New Job" to create a new posting.
    * **Edit Job**: Click the "Edit" icon (pencil) next to a job to modify its details or activate/deactivate it.
    * **Delete Job**: Click the "Delete" icon (trash can). If the job has applications, it will be deactivated instead of deleted.
5.  **Applications**:
    * **View Applications**: See a list of all job applications. Use filters to narrow down by status, job, or search for applicants by name, email, or Telegram username.
    * **View Details**: Click "View" next to an application to see the applicant's full profile, job details, and update the application status.
    * **Contact Applicant**: On the "View Application" page, use the "Send Email", "Call Phone", or "Send Telegram Message" buttons to contact the applicant.
    * **Download Resume**: If a resume file was uploaded, a "Download Resume File" button will appear, allowing you to download it directly from Telegram via the portal.
6.  **Users**:
    * **View Users**: See a list of all registered Telegram users. Use the search filter to find users by name, email, or Telegram username.
    * **View Profile**: Click the "Eye" icon next to a user to see their detailed profile and a list of their applications.
    * **Send Telegram Message**: On the "View User" page, use the "Send Telegram Message" button to send a direct message to that user via your bot.

## 8. Security Considerations

* **Change Default Credentials**: Immediately change the `ADMIN_USERNAME` and `ADMIN_PASSWORD` in your `project_root/env/.env` file from their defaults.
* **Strong `FLASK_SECRET_KEY`**: Ensure your `FLASK_SECRET_KEY` is long, random, and kept secret. Never share it or commit it to version control.
* **Production Deployment**: The Flask development server (`app.run(debug=True)`) is **not suitable for production**. For a production deployment, you must use a production-ready WSGI server like Gunicorn or uWSGI, and disable `FLASK_DEBUG` (`FLASK_DEBUG='False'` in `.env`).
* **Database Security**: For production, consider moving from SQLite to a more robust database (e.g., PostgreSQL) and securing its access credentials.
* **Bot Token Security**: Keep your `BOT_TOKEN` strictly confidential.
* **Input Sanitization**: While some basic validation is in place, comprehensive input sanitization is critical for any public-facing application to prevent SQL injection, XSS, etc.

## 9. Troubleshooting

* **`OSError: File not found` for `.env` or `jobs_bot.db`**:
    * Ensure your `.env` file is in `project_root/env/` and `jobs_bot.db` (if it exists) is in `project_root/db/`.
    * Verify the paths in `tg_bot/bot.py` and `web/app.py` for loading `.env` and connecting to `jobs_bot.db` are correct as per the latest code.
    * Make sure you are running the scripts from the correct directories (`tg_bot/` for `bot.py` and `web/` for `app.py`).
* **`sqlite3.OperationalError: unable to open database file`**:
    * This often means the database file doesn't exist or there are permission issues.
    * If it's the first run or you want to reset data, delete `project_root/db/jobs_bot.db` and restart.
    * Check file permissions for the `db` directory and `jobs_bot.db` file.
* **Telegram Bot not responding**:
    * Check your `BOT_TOKEN` in `.env` for typos.
    * Ensure the `bot.py` script is running in its terminal.
    * Check the terminal where `bot.py` is running for any error messages.
    * Verify your internet connection.
* **Web Portal not accessible**:
    * Ensure the `app.py` script is running in its terminal.
    * Check the terminal where `app.py` is running for any error messages.
    * Verify you are accessing the correct URL (`http://127.0.0.1:5000/`).
* **Resume forwarding not working**:
    * Double-check that `TELEGRAM_ADMIN_GROUP_ID` is correctly set in your `.env` file (remember it's a negative number for groups/channels).
    * Ensure your bot has been added to the Telegram group and has permission to send messages.
    * Check the bot's terminal for any error messages related to `send_document`.
* **`TemplateSyntaxError` in HTML templates**:
    * This usually means there's a typo or incorrect Jinja2 syntax in your HTML.
    * Carefully compare your HTML files with the provided code in the immersives, paying close attention to `{% ... %}` and `{{ ... }}` blocks, especially around `if` statements and loops. A single misplaced character can cause this.