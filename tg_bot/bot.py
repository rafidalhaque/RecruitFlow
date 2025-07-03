import logging
import sqlite3
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ConversationHandler, \
    ContextTypes, filters
import json
import os
from dotenv import load_dotenv  # Import find_dotenv
import re # For email validation
import uuid # For generating unique application IDs

# Construct the path to the .env file relative to the current script (bot.py)
# bot.py is in tg_bot/, .env is in env/ at project root
dotenv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'env', '.env')

# Load environment variables from the specified .env file
load_dotenv(dotenv_path, override=True, verbose=True) # Added override=True and verbose=True for debugging

TELEGRAM_ADMIN_GROUP_ID = os.getenv('TELEGRAM_ADMIN_GROUP_ID') # For forwarding resumes to tg group

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot token - Get from environment variables
BOT_TOKEN = os.getenv('BOT_TOKEN')

# Conversation states for profile creation
PROFILE_NAME, PROFILE_EMAIL, PROFILE_PHONE, PROFILE_EXPERIENCE, PROFILE_SKILLS, PROFILE_RESUME = range(6)


class JobsBot:
    def __init__(self):
        # Determine the path to the database file, now located in the 'db' directory
        # It's two levels up from tg_bot/bot.py, then into the 'db' folder
        self.db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'db', 'jobs_bot.db')
        self.init_database()

    def init_database(self):
        """Initialize SQLite database and create tables if they don't exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create users table for profiles
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                email TEXT,
                phone TEXT,
                experience TEXT,
                skills TEXT,
                resume_text TEXT,
                resume_file_id TEXT, -- New column for Telegram file_id
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Create jobs table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                requirements TEXT,
                location TEXT,
                salary TEXT,
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Create applications table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                public_application_id TEXT UNIQUE, -- New column for user-friendly ID
                user_id INTEGER,
                job_id INTEGER,
                status TEXT DEFAULT 'pending', -- e.g., 'pending', 'accepted', 'rejected', 'interviewed'
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id),
                FOREIGN KEY (job_id) REFERENCES jobs (id)
            )
        ''')

        # Insert sample jobs if the jobs table is empty
        cursor.execute("SELECT COUNT(*) FROM jobs")
        if cursor.fetchone()[0] == 0:
            sample_jobs = [
                ("Software Developer", "Full-stack developer position", "Python, JavaScript, React", "Remote",
                 "$60,000-80,000"),
                ("Data Analyst", "Analyze business data and create reports", "SQL, Excel, Python", "New York",
                 "$50,000-70,000"),
                ("Marketing Manager", "Lead marketing campaigns", "Digital Marketing, SEO, Social Media", "California",
                 "$55,000-75,000"),
                ("UI/UX Designer", "Design user interfaces and experiences", "Figma, Adobe XD, Prototyping", "Remote",
                 "$45,000-65,000")
            ]
            cursor.executemany(
                "INSERT INTO jobs (title, description, requirements, location, salary) VALUES (?, ?, ?, ?, ?)",
                sample_jobs
            )
            logger.info("Inserted sample jobs into the database.")

        conn.commit()
        conn.close()

    def get_user_profile(self, user_id):
        """Retrieve a user's profile from the database by user_id."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        profile = cursor.fetchone()
        conn.close()
        return profile

    def save_user_profile(self, user_id, username, profile_data):
        """Save or update a user's profile in the database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
        exists = cursor.fetchone()

        # get resume file id
        resume_file_id = profile_data.get('resume_file_id')

        if exists:
            # Update existing profile
            cursor.execute('''
                UPDATE users SET username=?, full_name=?, email=?, phone=?,
                experience=?, skills=?, resume_text=?, resume_file_id=?, updated_at=CURRENT_TIMESTAMP
                WHERE user_id=?
            ''', (username, profile_data['name'], profile_data['email'],
                  profile_data['phone'], profile_data['experience'],
                  profile_data['skills'], profile_data['resume'], resume_file_id, user_id))
            logger.info(f"Updated profile for user_id: {user_id}")
        else:
            # Insert new profile
            cursor.execute('''
                INSERT INTO users (user_id, username, full_name, email, phone,
                experience, skills, resume_text, resume_file_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, username, profile_data['name'], profile_data['email'],
                  profile_data['phone'], profile_data['experience'],
                  profile_data['skills'], profile_data['resume'], resume_file_id))
            logger.info(f"Created new profile for user_id: {user_id}")

        conn.commit()
        conn.close()

    def get_active_jobs(self):
        """Retrieve all active job postings from the database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM jobs WHERE is_active = 1 ORDER BY created_at DESC")
        jobs = cursor.fetchall()
        conn.close()
        return jobs

    def apply_for_job(self, user_id, job_id):
        """Submit a job application for a user."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Check if the user has already applied for this job
        cursor.execute("SELECT id FROM applications WHERE user_id = ? AND job_id = ?", (user_id, job_id))
        if cursor.fetchone():
            conn.close()
            logger.warning(f"User {user_id} already applied for job {job_id}.")
            return False, "You have already applied for this position!", None

        # Generate a unique public application ID
        public_app_id = str(uuid.uuid4()).split('-')[0].upper() # Use first part of UUID for brevity

        # Insert new application
        cursor.execute("INSERT INTO applications (public_application_id, user_id, job_id) VALUES (?, ?, ?)",
                       (public_app_id, user_id, job_id))
        conn.commit()
        conn.close()
        logger.info(f"User {user_id} successfully applied for job {job_id}.")
        return True, "Application submitted successfully!", public_app_id

# Initialize the JobsBot instance globally
jobs_bot = JobsBot()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /start command, showing the main menu."""
    keyboard = [
        [KeyboardButton("📝 Create/Update Profile")],
        [KeyboardButton("💼 View Jobs"), KeyboardButton("📋 My Applications")],
        [KeyboardButton("ℹ️ Help")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    welcome_text = """
🤖 Welcome to Jobs Bot!

I can help you find and apply for jobs. Here's what you can do:

📝 *Create/Update Profile* - Set up your professional profile
💼 *View Jobs* - Browse available job positions
📋 *My Applications* - Check your application status
ℹ️ *Help* - Get assistance

Start by creating your profile to apply for jobs with one click!
    """
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')
    logger.info(f"User {update.effective_user.id} started the bot.")


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles clicks on the main menu reply keyboard buttons."""
    text = update.message.text

    if text == "📝 Create/Update Profile":
        await create_profile(update, context)
    elif text == "💼 View Jobs":
        await view_jobs(update, context)
    elif text == "📋 My Applications":
        await my_applications(update, context)
    elif text == "ℹ️ Help":
        await help_command(update, context)
    else:
        await update.message.reply_text("I didn't understand that. Please use the menu buttons.")
    logger.info(f"User {update.effective_user.id} clicked button: {text}")


async def create_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Starts the conversation for creating or updating a user profile."""
    user_id = update.effective_user.id
    profile = jobs_bot.get_user_profile(user_id)

    if profile:
        # Show existing data including resume_file_id if present
        resume_info = "Not provided"
        if profile[7]:  # resume_text
            resume_info = profile[7][:50] + "..." if len(profile[7]) > 50 else profile[7]
        if profile[8]:  # resume_file_id
            resume_info += f"\n(File ID: {profile[8][:10]}...)"
        # If profile exists, inform the user and show current data
        await update.message.reply_text(
            f"📝 Updating your existing profile:\n\n"
            f"Name: {profile[2]}\n"
            f"Email: {profile[3]}\n"
            f"Phone: {profile[4]}\n"
            f"Experience: {profile[5]}\n"
            f"Skills: {profile[6]}\n"
            f"Resume: {profile[7][:50]}...\n\n"  # Show first 50 chars of resume
            f"Let's update your information. What's your full name?"
        )
    else:
        # If no profile, start a new creation process
        await update.message.reply_text(
            "📝 Let's create your professional profile!\n\n"
            "This information will be used for job applications.\n\n"
            "What's your full name?"
        )
    context.user_data['profile'] = {}  # Initialize user_data for the profile
    context.user_data['profile']['resume_file_id'] = None  # Initialize resume_file_id
    logger.info(f"User {user_id} started profile creation/update.")
    return PROFILE_NAME


async def profile_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Collects the user's full name for their profile."""
    context.user_data['profile']['name'] = update.message.text
    await update.message.reply_text("📧 What's your email address?")
    return PROFILE_EMAIL


async def profile_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Collects the user's email address for their profile."""
    email = update.message.text
    # Basic email regex validation
    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        await update.message.reply_text("❌ That doesn't look like a valid email address. Please try again:")
        return PROFILE_EMAIL  # Stay in the same state
    context.user_data['profile']['email'] = email
    await update.message.reply_text("📱 What's your phone number?")
    return PROFILE_PHONE


async def profile_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Collects the user's phone number for their profile."""
    context.user_data['profile']['phone'] = update.message.text
    await update.message.reply_text("💼 Tell me about your work experience (e.g., '5 years as a Software Engineer'):")
    return PROFILE_EXPERIENCE


async def profile_experience(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Collects the user's work experience for their profile."""
    context.user_data['profile']['experience'] = update.message.text
    await update.message.reply_text("🔧 What are your key skills? (e.g., 'Python, SQL, Project Management')")
    return PROFILE_SKILLS


async def profile_skills(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Collects the user's skills for their profile."""
    context.user_data['profile']['skills'] = update.message.text
    await update.message.reply_text("📄 Please provide a brief resume/bio about yourself (max 500 characters):")
    return PROFILE_RESUME


# Line 253 (start of profile_resume function)
async def profile_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles the user's resume input. Accepts either text or a document.
    If a document is uploaded, stores its file_id and forwards it to the admin group.
    """
    if update.message.document:
        # User uploaded a file
        file_id = update.message.document.file_id
        file_name = update.message.document.file_name
        context.user_data['profile']['resume_file_id'] = file_id
        context.user_data['profile']['resume'] = f"Uploaded file: {file_name}"  # Store a placeholder text

        # Forward the document to the admin group/channel
        if TELEGRAM_ADMIN_GROUP_ID:
            try:
                await context.bot.send_document(
                    chat_id=TELEGRAM_ADMIN_GROUP_ID,
                    document=file_id,
                    caption=f"New Resume Uploaded!\n\n"
                            f"From User: {update.effective_user.full_name} (@{update.effective_user.username or 'N/A'})\n"
                            f"User ID: {update.effective_user.id}\n"
                            f"File Name: {file_name}\n"
                            f"File ID: `{file_id}`"  # Display file_id for admin reference
                )
                await update.message.reply_text("📄 Resume file received and forwarded to admin. Thank you!")
                logger.info(
                    f"User {update.effective_user.id} uploaded resume file {file_name} (ID: {file_id}). Forwarded to admin group.")
            except Exception as e:
                logger.error(f"Failed to forward resume file {file_id} to admin group: {e}")
                await update.message.reply_text(
                    "⚠️ There was an error forwarding your resume file to the admin. Please try again or contact support.")
                # Don't end conversation, allow retry or text input
                return PROFILE_RESUME
        else:
            await update.message.reply_text("📄 Resume file received. Admin group for forwarding is not configured.")
            logger.warning("TELEGRAM_ADMIN_GROUP_ID is not configured. Resume file not forwarded.")

    elif update.message.text:
        # User provided text for resume/bio
        context.user_data['profile']['resume'] = update.message.text
        context.user_data['profile']['resume_file_id'] = None  # Ensure no old file_id is kept

    else:
        await update.message.reply_text("Please send your resume as text or upload a document (PDF, DOCX, etc.):")
        return PROFILE_RESUME  # Stay in the same state if neither text nor document received

async def view_jobs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays a list of available job positions using inline keyboard buttons."""
    jobs = jobs_bot.get_active_jobs()

    if not jobs:
        await update.message.reply_text("😔 No jobs available at the moment. Please check back later!")
        return

    keyboard = []
    for job in jobs:
        job_id, title, description, requirements, location, salary, is_active, created_at = job
        keyboard.append([InlineKeyboardButton(
            f"💼 {title} - {location}",
            callback_data=f"job_{job_id}"  # Callback data includes job ID
        )])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "💼 Available Job Positions:\n\nClick on any job to view details and apply:",
        reply_markup=reply_markup
    )
    logger.info(f"User {update.effective_user.id} viewed available jobs.")


async def job_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles callbacks from inline keyboard buttons (job selection and application)."""
    query = update.callback_query
    await query.answer()  # Acknowledge the callback query

    callback_data = query.data

    if callback_data.startswith("job_"):
        job_id = int(callback_data.split("_")[1])
        await show_job_details(query, job_id)
        logger.info(f"User {query.from_user.id} viewed details for job {job_id}.")
    elif callback_data.startswith("apply_"):
        job_id = int(callback_data.split("_")[1])
        await apply_job(query, job_id)
        logger.info(f"User {query.from_user.id} attempted to apply for job {job_id}.")
    elif callback_data == "back_jobs":
        # Re-show the list of jobs
        await view_jobs(query, context)  # Pass query as update to reuse view_jobs logic
        logger.info(f"User {query.from_user.id} navigated back to job list.")
    elif callback_data == "create_profile":
        # Redirect to profile creation, using the message context
        # For simplicity, we'll send a new message prompting them to use the main menu button
        await query.edit_message_text(
            "Please use the '📝 Create/Update Profile' button from the main menu to create your profile."
        )
        logger.info(f"User {query.from_user.id} was prompted to create profile via main menu.")


async def show_job_details(query, job_id):
    """Displays detailed information about a selected job."""
    conn = sqlite3.connect(jobs_bot.db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
    job = cursor.fetchone()
    conn.close()

    if not job:
        await query.edit_message_text("❌ Job not found!")
        logger.warning(f"Job {job_id} not found for details view.")
        return

    job_id, title, description, requirements, location, salary, is_active, created_at = job

    job_text = f"""
💼 **{title}**

📍 **Location:** {location if location else 'রিমোট'}
💰 **Salary:** {salary if salary else 'রব্বুল আ\'লামীনের সন্তুষ্টি'}

📋 **Description:**
{description if description else 'No description provided.'}

🔧 **Requirements:**
{requirements if requirements else 'No specific requirements listed.'}
    """

    # Check if user has a profile to determine if 'Apply Now' button should be shown
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


async def apply_job(query, job_id):
    """Handles the job application process."""
    user_id = query.from_user.id

    # Ensure user has a profile before allowing application
    profile = jobs_bot.get_user_profile(user_id)
    if not profile:
        await query.edit_message_text(
            "❌ Please create your profile first before applying!\n\n"
            "Use '📝 Create/Update Profile' from the main menu."
        )
        logger.warning(f"User {user_id} tried to apply for job {job_id} without a profile.")
        return

    # Attempt to apply for the job
    success, message = jobs_bot.apply_for_job(user_id, job_id)

    if success:
        await query.edit_message_text(
            f"🎉 {message}\n\nYour application has been submitted and will be reviewed by our team.")
    else:
        await query.edit_message_text(f"⚠️ {message}")
    logger.info(f"Application attempt for job {job_id} by user {user_id}: Success={success}, Message='{message}'")


async def my_applications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays a list of the user's submitted job applications."""
    user_id = update.effective_user.id

    conn = sqlite3.connect(jobs_bot.db_path)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT j.title, j.location, a.status, a.applied_at, a.public_application_id
        FROM applications a
        JOIN jobs j ON a.job_id = j.id
        WHERE a.user_id = ?
        ORDER BY a.applied_at DESC
    ''', (user_id,))
    applications = cursor.fetchall()
    conn.close()

    if not applications:
        await update.message.reply_text(
            "📋 You haven't applied for any jobs yet.\n\nUse '💼 View Jobs' to browse and apply!")
        logger.info(f"User {user_id} has no applications.")
        return

    text = "📋 **Your Job Applications:**\n\n"
    for app in applications:
        title, location, status, applied_at, public_app_id = app
        # Determine emoji based on application status
        status_emoji = "⏳" if status == "pending" else "✅" if status == "accepted" else "❌" if status == "rejected" else "🤝" if status == "interviewed" else "❓"
        text += f"{status_emoji} **{title}** - {location}\n"
        text += f"   Status: {status.title()}\n"
        text += f"   Applied: {applied_at[:10]}\n\n"  # Format date to INSEE-MM-DD
        text += f"   Application ID: `{public_app_id}`\n"  # Display public_app_id

    await update.message.reply_text(text, parse_mode='Markdown')
    logger.info(f"User {user_id} viewed their applications.")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Provides help information about the bot's features."""
    help_text = """
🤖 **Jobs Bot Help**

**Available Commands:**
• `/start` - Start the bot and see main menu

**Main Features:**
📝 **Create/Update Profile** - Set up your professional information (name, email, phone, experience, skills, resume). You can upload your resume as a file!
💼 **View Jobs** - Browse available job positions and apply with one click
📋 **My Applications** - Check the status of your submitted job applications, including your unique Application ID.
ℹ️ **Help** - Show this help message

**How to Apply for Jobs:**
1. First, create or update your profile using the '📝 Create/Update Profile' button.
2. Browse available jobs using the '💼 View Jobs' button.
3. Click on any job in the list to see its details.
4. If you have a profile, an '✅ Apply Now' button will appear. Click it to apply!

**Need Support?**
Contact @cstcontactbot if you have any issues or questions.
    """
    await update.message.reply_text(help_text, parse_mode='Markdown')
    logger.info(f"User {update.effective_user.id} requested help.")


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancels the current conversation (e.g., profile creation)."""
    await update.message.reply_text(
        "❌ Operation cancelled. You can use the main menu buttons to continue.",
        reply_markup=ReplyKeyboardMarkup([
            [KeyboardButton("📝 Create/Update Profile")],
            [KeyboardButton("💼 View Jobs"), KeyboardButton("📋 My Applications")],
            [KeyboardButton("ℹ️ Help")]
        ], resize_keyboard=True)
    )
    logger.info(f"User {update.effective_user.id} cancelled a conversation.")
    return ConversationHandler.END


def main():
    """Starts the Telegram bot application."""
    # Ensure BOT_TOKEN is loaded
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN environment variable not set. Please set it in your .env file.")
        print("Error: BOT_TOKEN environment variable not set. Please set it in your .env file.")
        return

    # Create the Application and pass your bot's token.
    application = Application.builder().token(BOT_TOKEN).build()

    # Define the ConversationHandler for profile creation
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
        fallbacks=[CommandHandler('cancel', cancel)],  # Allow users to cancel the conversation
    )

    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(profile_conv_handler)  # Add the conversation handler
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,
                                           button_handler))  # Handles all text messages that are not commands
    application.add_handler(CallbackQueryHandler(job_callback))  # Handles inline keyboard button presses

    # Start the Bot
    print("🤖 Jobs Bot is starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)  # Poll for updates from Telegram


if __name__ == '__main__':
    main()
