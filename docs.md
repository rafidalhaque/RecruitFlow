# Telegram Jobs Bot - Complete Code Documentation

## Table of Contents
1. [Overview](#overview)
2. [Dependencies and Setup](#dependencies-and-setup)
3. [Database Schema](#database-schema)
4. [Class Structure](#class-structure)
5. [Bot Handlers](#bot-handlers)
6. [Conversation Flow](#conversation-flow)
7. [Detailed Code Explanation](#detailed-code-explanation)
8. [Usage Instructions](#usage-instructions)

## Overview

This Telegram bot is designed to facilitate job searching and application processes. It allows users to:
- Create and manage professional profiles
- Browse available job positions
- Apply for jobs with one-click using saved profile data
- Track application status

The bot uses SQLite database for data persistence and implements conversation handlers for interactive user experiences.

## Dependencies and Setup

```python
import logging
import sqlite3
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ConversationHandler, ContextTypes, filters
import json
```

### Dependencies Explanation:
- **`logging`**: Built-in Python module for logging system events and errors
- **`sqlite3`**: Built-in database interface for SQLite databases
- **`datetime`**: For handling date and time operations
- **`telegram`**: Core Telegram Bot API components for UI elements
- **`telegram.ext`**: Extension module with handlers and application management
- **`json`**: For potential JSON data handling (future use)

### Logging Configuration:
```python
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)
```
- Sets up logging with timestamp, logger name, level, and message format
- Log level set to INFO to capture important events
- Creates a logger instance for this module

### Bot Configuration:
```python
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"
```
- Placeholder for the actual bot token from BotFather
- **Important**: Replace with your actual token before running

### Conversation States:
```python
PROFILE_NAME, PROFILE_EMAIL, PROFILE_PHONE, PROFILE_EXPERIENCE, PROFILE_SKILLS, PROFILE_RESUME = range(6)
```
- Defines conversation states for profile creation flow
- Each constant represents a step in the profile creation process
- `range(6)` creates integers 0-5 for each state

## Database Schema

The bot uses three main tables:

### 1. Users Table
```sql
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,           -- Telegram user ID (unique identifier)
    username TEXT,                         -- Telegram username
    full_name TEXT,                        -- User's full name
    email TEXT,                           -- Email address
    phone TEXT,                           -- Phone number
    experience TEXT,                      -- Work experience description
    skills TEXT,                          -- Skills list
    resume_text TEXT,                     -- Resume/bio text
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- Profile creation time
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP   -- Last update time
)
```

### 2. Jobs Table
```sql
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,  -- Auto-incrementing job ID
    title TEXT NOT NULL,                   -- Job title (required)
    description TEXT,                      -- Job description
    requirements TEXT,                     -- Job requirements
    location TEXT,                        -- Job location
    salary TEXT,                          -- Salary information
    is_active BOOLEAN DEFAULT 1,          -- Job active status (1=active, 0=inactive)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP  -- Job posting time
)
```

### 3. Applications Table
```sql
CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,  -- Auto-incrementing application ID
    user_id INTEGER,                       -- Reference to users table
    job_id INTEGER,                        -- Reference to jobs table
    status TEXT DEFAULT 'pending',        -- Application status
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- Application time
    FOREIGN KEY (user_id) REFERENCES users (user_id),    -- Foreign key constraint
    FOREIGN KEY (job_id) REFERENCES jobs (id)             -- Foreign key constraint
)
```

## Class Structure

### JobsBot Class

```python
class JobsBot:
    def __init__(self):
        self.init_database()
```
- Main class that encapsulates all bot functionality
- Constructor calls database initialization

#### Database Initialization Method
```python
def init_database(self):
    """Initialize SQLite database"""
    conn = sqlite3.connect('jobs_bot.db')
    cursor = conn.cursor()
```
- Creates connection to SQLite database file
- Creates cursor object for executing SQL commands
- Database file is created automatically if it doesn't exist

#### Sample Data Insertion
```python
cursor.execute("SELECT COUNT(*) FROM jobs")
if cursor.fetchone()[0] == 0:
    sample_jobs = [
        ("Software Developer", "Full-stack developer position", "Python, JavaScript, React", "Remote", "$60,000-80,000"),
        # ... more sample jobs
    ]
    cursor.executemany(
        "INSERT INTO jobs (title, description, requirements, location, salary) VALUES (?, ?, ?, ?, ?)",
        sample_jobs
    )
```
- Checks if jobs table is empty
- Inserts sample job data if no jobs exist
- Uses parameterized queries to prevent SQL injection

#### Profile Management Methods

##### Get User Profile
```python
def get_user_profile(self, user_id):
    """Get user profile from database"""
    conn = sqlite3.connect('jobs_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    profile = cursor.fetchone()
    conn.close()
    return profile
```
- Retrieves user profile data by user_id
- Returns tuple with all user data or None if not found
- Always closes database connection after use

##### Save User Profile
```python
def save_user_profile(self, user_id, username, profile_data):
    """Save or update user profile"""
    conn = sqlite3.connect('jobs_bot.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    exists = cursor.fetchone()
```
- First checks if user profile exists
- Uses UPDATE if profile exists, INSERT if new user
- Handles both profile creation and updates

#### Job Management Methods

##### Get Active Jobs
```python
def get_active_jobs(self):
    """Get all active jobs"""
    conn = sqlite3.connect('jobs_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM jobs WHERE is_active = 1 ORDER BY created_at DESC")
    jobs = cursor.fetchall()
    conn.close()
    return jobs
```
- Retrieves only active jobs (is_active = 1)
- Orders by creation date (newest first)
- Returns list of tuples containing job data

##### Apply for Job
```python
def apply_for_job(self, user_id, job_id):
    """Submit job application"""
    conn = sqlite3.connect('jobs_bot.db')
    cursor = conn.cursor()
    
    # Check if already applied
    cursor.execute("SELECT id FROM applications WHERE user_id = ? AND job_id = ?", (user_id, job_id))
    if cursor.fetchone():
        conn.close()
        return False, "You have already applied for this position!"
```
- Prevents duplicate applications
- Returns tuple: (success_boolean, message_string)
- Inserts new application record if not already applied

## Bot Handlers

### Start Command Handler
```python
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    keyboard = [
        [KeyboardButton("📝 Create/Update Profile")],
        [KeyboardButton("💼 View Jobs"), KeyboardButton("📋 My Applications")],
        [KeyboardButton("ℹ️ Help")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
```
- Creates custom keyboard with main menu options
- `resize_keyboard=True` makes keyboard fit screen better
- Uses emojis for better visual appeal

### Button Handler
```python
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button clicks"""
    text = update.message.text
    
    if text == "📝 Create/Update Profile":
        await create_profile(update, context)
    elif text == "💼 View Jobs":
        await view_jobs(update, context)
    # ... more conditions
```
- Routes button clicks to appropriate handler functions
- Uses exact string matching for button text
- Calls corresponding async functions for each action

## Conversation Flow

### Profile Creation Flow

#### Step 1: Initialize Profile Creation
```python
async def create_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start profile creation conversation"""
    user_id = update.effective_user.id
    profile = jobs_bot.get_user_profile(user_id)
    
    if profile:
        await update.message.reply_text(
            f"📝 Updating your existing profile:\n\n"
            f"Name: {profile[2]}\n"
            f"Email: {profile[3]}\n"
            f"Phone: {profile[4]}\n\n"
            f"Let's update your information. What's your full name?"
        )
    else:
        await update.message.reply_text(
            "📝 Let's create your professional profile!\n\n"
            "This information will be used for job applications.\n\n"
            "What's your full name?"
        )
    
    return PROFILE_NAME
```
- Checks if user already has a profile
- Shows existing data if updating
- Returns next conversation state
- Different messages for new vs. existing profiles

#### Step 2-6: Collect Profile Information
```python
async def profile_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle name input"""
    context.user_data['profile'] = {'name': update.message.text}
    await update.message.reply_text("📧 What's your email address?")
    return PROFILE_EMAIL
```
- Stores user input in context.user_data dictionary
- Each step collects one piece of information
- Returns next conversation state
- Pattern repeats for each profile field

#### Final Step: Save Profile
```python
async def profile_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle resume input and save profile"""
    context.user_data['profile']['resume'] = update.message.text
    
    user_id = update.effective_user.id
    username = update.effective_user.username or "N/A"
    
    jobs_bot.save_user_profile(user_id, username, context.user_data['profile'])
    
    await update.message.reply_text(
        "✅ Profile saved successfully!\n\n"
        "You can now apply for jobs with one click. Use '💼 View Jobs' to browse available positions."
    )
    
    return ConversationHandler.END
```
- Saves final piece of profile data
- Calls save_user_profile method
- Ends conversation with ConversationHandler.END
- Provides next steps to user

### Job Browsing and Application

#### View Jobs Function
```python
async def view_jobs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show available jobs with inline keyboard"""
    jobs = jobs_bot.get_active_jobs()
    
    if not jobs:
        await update.message.reply_text("😔 No jobs available at the moment. Please check back later!")
        return
    
    keyboard = []
    for job in jobs:
        job_id, title, description, requirements, location, salary = job[:6]
        keyboard.append([InlineKeyboardButton(
            f"💼 {title} - {location}", 
            callback_data=f"job_{job_id}"
        )])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "💼 Available Job Positions:\n\nClick on any job to view details and apply:",
        reply_markup=reply_markup
    )
```
- Retrieves active jobs from database
- Creates inline keyboard with job buttons
- Each button has callback_data with job ID
- Handles case when no jobs are available

#### Job Callback Handler
```python
async def job_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle job selection callbacks"""
    query = update.callback_query
    await query.answer()
    
    callback_data = query.data
    
    if callback_data.startswith("job_"):
        job_id = int(callback_data.split("_")[1])
        await show_job_details(query, job_id)
    elif callback_data.startswith("apply_"):
        job_id = int(callback_data.split("_")[1])
        await apply_job(query, job_id)
```
- Handles inline button callbacks
- `query.answer()` removes loading indicator
- Parses callback_data to determine action
- Routes to appropriate function based on prefix

#### Show Job Details Function
```python
async def show_job_details(query, job_id):
    """Show detailed job information"""
    conn = sqlite3.connect('jobs_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
    job = cursor.fetchone()
    conn.close()
    
    if not job:
        await query.edit_message_text("❌ Job not found!")
        return
    
    job_id, title, description, requirements, location, salary = job[:6]
    
    job_text = f"""
💼 **{title}**

📍 **Location:** {location}
💰 **Salary:** {salary}

📋 **Description:**
{description}

🔧 **Requirements:**
{requirements}
    """
    
    # Check if user has profile
    user_id = query.from_user.id
    profile = jobs_bot.get_user_profile(user_id)
    
    keyboard = []
    if profile:
        keyboard.append([InlineKeyboardButton("✅ Apply Now", callback_data=f"apply_{job_id}")])
    else:
        keyboard.append([InlineKeyboardButton("📝 Create Profile First", callback_data="create_profile")])
    
    keyboard.append([InlineKeyboardButton("🔙 Back to Jobs", callback_data="back_jobs")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(job_text, reply_markup=reply_markup, parse_mode='Markdown')
```
- Fetches specific job details from database
- Formats job information with emojis and markdown
- Checks if user has profile to determine available actions
- Creates appropriate inline keyboard based on user status
- Uses `edit_message_text` to update existing message

#### Apply for Job Function
```python
async def apply_job(query, job_id):
    """Apply for a job"""
    user_id = query.from_user.id
    
    # Check if user has profile
    profile = jobs_bot.get_user_profile(user_id)
    if not profile:
        await query.edit_message_text(
            "❌ Please create your profile first before applying!\n\n"
            "Use '📝 Create/Update Profile' from the main menu."
        )
        return
    
    # Apply for job
    success, message = jobs_bot.apply_for_job(user_id, job_id)
    
    if success:
        await query.edit_message_text(f"🎉 {message}\n\nYour application has been submitted and will be reviewed by our team.")
    else:
        await query.edit_message_text(f"⚠️ {message}")
```
- Validates user has profile before allowing application
- Calls apply_for_job method which handles duplicate checking
- Provides appropriate feedback based on success/failure
- Updates message with application status

### Application Tracking

#### My Applications Function
```python
async def my_applications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's job applications"""
    user_id = update.effective_user.id
    
    conn = sqlite3.connect('jobs_bot.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT j.title, j.location, a.status, a.applied_at 
        FROM applications a 
        JOIN jobs j ON a.job_id = j.id 
        WHERE a.user_id = ? 
        ORDER BY a.applied_at DESC
    ''', (user_id,))
    applications = cursor.fetchall()
    conn.close()
    
    if not applications:
        await update.message.reply_text("📋 You haven't applied for any jobs yet.\n\nUse '💼 View Jobs' to browse and apply!")
        return
    
    text = "📋 **Your Job Applications:**\n\n"
    for app in applications:
        title, location, status, applied_at = app
        status_emoji = "⏳" if status == "pending" else "✅" if status == "accepted" else "❌"
        text += f"{status_emoji} **{title}** - {location}\n"
        text += f"   Status: {status.title()}\n"
        text += f"   Applied: {applied_at[:10]}\n\n"
    
    await update.message.reply_text(text, parse_mode='Markdown')
```
- Uses JOIN query to get job details with application info
- Orders by application date (newest first)
- Handles case when user has no applications
- Uses emojis to indicate application status visually
- Formats date to show only YYYY-MM-DD portion

## Main Application Setup

### Conversation Handler Configuration
```python
profile_conv_handler = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^📝 Create/Update Profile$"), create_profile)],
    states={
        PROFILE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, profile_name)],
        PROFILE_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, profile_email)],
        PROFILE_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, profile_phone)],
        PROFILE_EXPERIENCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, profile_experience)],
        PROFILE_SKILLS: [MessageHandler(filters.TEXT & ~filters.COMMAND, profile_skills)],
        PROFILE_RESUME: [MessageHandler(filters.TEXT & ~filters.COMMAND, profile_resume)],
    },
    fallbacks=[CommandHandler('cancel', cancel)],
)
```
- Defines conversation flow for profile creation
- `entry_points`: How conversation starts (specific button press)
- `states`: Maps each conversation state to handler function
- `filters.TEXT & ~filters.COMMAND`: Accepts text but not commands
- `fallbacks`: How to exit conversation (cancel command)

### Application Builder and Handler Registration
```python
def main():
    """Start the bot"""
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(profile_conv_handler)
    application.add_handler(MessageHandler(filters.TEXT, button_handler))
    application.add_handler(CallbackQueryHandler(job_callback))
    
    # Start the bot
    print("🤖 Jobs Bot is starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)
```
- Creates bot application with token
- Registers all handlers in specific order (important!)
- ConversationHandler should be registered before general MessageHandler
- `run_polling()` starts the bot and keeps it running
- `allowed_updates=Update.ALL_TYPES` processes all update types

## Usage Instructions

### 1. Setup Requirements
```bash
pip install python-telegram-bot
```

### 2. Bot Token Setup
1. Message @BotFather on Telegram
2. Send `/newbot` command
3. Follow instructions to create bot
4. Copy the provided token
5. Replace `YOUR_BOT_TOKEN_HERE` in the code

### 3. Running the Bot
```bash
python jobs_bot.py
```

### 4. Bot Features Usage

#### For Job Seekers:
1. **Start**: Send `/start` to see main menu
2. **Create Profile**: Click "📝 Create/Update Profile" and follow prompts
3. **Browse Jobs**: Click "💼 View Jobs" to see available positions
4. **Apply**: Click on any job to see details and apply with one click
5. **Track Applications**: Click "📋 My Applications" to see status

#### For Administrators (Future Web Portal):
- Add new job postings through web interface
- View applications and applicant details
- Manage job status (active/inactive)
- Contact applicants directly

## Error Handling and Best Practices

### Database Connection Management
- Always close database connections after use
- Use try-except blocks for database operations (can be added)
- Use parameterized queries to prevent SQL injection

### User Input Validation
- Check for profile existence before allowing applications
- Prevent duplicate applications
- Handle empty job lists gracefully

### Message Formatting
- Use markdown for better text formatting
- Include emojis for visual appeal
- Provide clear instructions and feedback

### Security Considerations
- Bot token should be kept secret
- Database should be secured in production
- Input sanitization for all user data
- Rate limiting can be implemented for production use

This documentation covers every aspect of the Telegram Jobs Bot code, from basic setup to advanced functionality. The bot is designed to be user-friendly while maintaining robust data management and error handling.