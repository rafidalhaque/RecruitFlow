import logging
import sqlite3
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ConversationHandler, \
    ContextTypes, filters
import json

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot token - Replace with your actual bot token
BOT_TOKEN = "7790842099:AAEk2q9BGDzQXyrDQpIBD7781PQnRq5s52g"

# Conversation states
PROFILE_NAME, PROFILE_EMAIL, PROFILE_PHONE, PROFILE_EXPERIENCE, PROFILE_SKILLS, PROFILE_RESUME = range(6)


class JobsBot:
    def __init__(self):
        self.init_database()

    def init_database(self):
        """Initialize SQLite database"""
        conn = sqlite3.connect('jobs_bot.db')
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
                user_id INTEGER,
                job_id INTEGER,
                status TEXT DEFAULT 'pending',
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id),
                FOREIGN KEY (job_id) REFERENCES jobs (id)
            )
        ''')

        # Insert sample jobs if table is empty
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

        conn.commit()
        conn.close()

    def get_user_profile(self, user_id):
        """Get user profile from database"""
        conn = sqlite3.connect('jobs_bot.db')
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        profile = cursor.fetchone()
        conn.close()
        return profile

    def save_user_profile(self, user_id, username, profile_data):
        """Save or update user profile"""
        conn = sqlite3.connect('jobs_bot.db')
        cursor = conn.cursor()

        cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
        exists = cursor.fetchone()

        if exists:
            cursor.execute('''
                UPDATE users SET username=?, full_name=?, email=?, phone=?, 
                experience=?, skills=?, resume_text=?, updated_at=CURRENT_TIMESTAMP
                WHERE user_id=?
            ''', (username, profile_data['name'], profile_data['email'],
                  profile_data['phone'], profile_data['experience'],
                  profile_data['skills'], profile_data['resume'], user_id))
        else:
            cursor.execute('''
                INSERT INTO users (user_id, username, full_name, email, phone, 
                experience, skills, resume_text) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, username, profile_data['name'], profile_data['email'],
                  profile_data['phone'], profile_data['experience'],
                  profile_data['skills'], profile_data['resume']))

        conn.commit()
        conn.close()

    def get_active_jobs(self):
        """Get all active jobs"""
        conn = sqlite3.connect('jobs_bot.db')
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM jobs WHERE is_active = 1 ORDER BY created_at DESC")
        jobs = cursor.fetchall()
        conn.close()
        return jobs

    def apply_for_job(self, user_id, job_id):
        """Submit job application"""
        conn = sqlite3.connect('jobs_bot.db')
        cursor = conn.cursor()

        # Check if already applied
        cursor.execute("SELECT id FROM applications WHERE user_id = ? AND job_id = ?", (user_id, job_id))
        if cursor.fetchone():
            conn.close()
            return False, "You have already applied for this position!"

        cursor.execute("INSERT INTO applications (user_id, job_id) VALUES (?, ?)", (user_id, job_id))
        conn.commit()
        conn.close()
        return True, "Application submitted successfully!"


# Initialize bot instance
jobs_bot = JobsBot()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    keyboard = [
        [KeyboardButton("📝 Create/Update Profile")],
        [KeyboardButton("💼 View Jobs"), KeyboardButton("📋 My Applications")],
        [KeyboardButton("ℹ️ Help")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    welcome_text = """
🤖 Welcome to Jobs Bot!

I can help you find and apply for jobs. Here's what you can do:

📝 Create/Update Profile - Set up your professional profile
💼 View Jobs - Browse available job positions
📋 My Applications - Check your application status
ℹ️ Help - Get assistance

Start by creating your profile to apply for jobs with one click!
    """

    await update.message.reply_text(welcome_text, reply_markup=reply_markup)


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button clicks"""
    text = update.message.text

    if text == "📝 Create/Update Profile":
        await create_profile(update, context)
    elif text == "💼 View Jobs":
        await view_jobs(update, context)
    elif text == "📋 My Applications":
        await my_applications(update, context)
    elif text == "ℹ️ Help":
        await help_command(update, context)


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


async def profile_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle name input"""
    context.user_data['profile'] = {'name': update.message.text}
    await update.message.reply_text("📧 What's your email address?")
    return PROFILE_EMAIL


async def profile_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle email input"""
    context.user_data['profile']['email'] = update.message.text
    await update.message.reply_text("📱 What's your phone number?")
    return PROFILE_PHONE


async def profile_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle phone input"""
    context.user_data['profile']['phone'] = update.message.text
    await update.message.reply_text("💼 Tell me about your work experience (years and type):")
    return PROFILE_EXPERIENCE


async def profile_experience(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle experience input"""
    context.user_data['profile']['experience'] = update.message.text
    await update.message.reply_text("🔧 What are your key skills? (separate with commas)")
    return PROFILE_SKILLS


async def profile_skills(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle skills input"""
    context.user_data['profile']['skills'] = update.message.text
    await update.message.reply_text("📄 Please provide a brief resume/bio about yourself:")
    return PROFILE_RESUME


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
        await query.edit_message_text(
            f"🎉 {message}\n\nYour application has been submitted and will be reviewed by our team.")
    else:
        await query.edit_message_text(f"⚠️ {message}")


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
        await update.message.reply_text(
            "📋 You haven't applied for any jobs yet.\n\nUse '💼 View Jobs' to browse and apply!")
        return

    text = "📋 **Your Job Applications:**\n\n"
    for app in applications:
        title, location, status, applied_at = app
        status_emoji = "⏳" if status == "pending" else "✅" if status == "accepted" else "❌"
        text += f"{status_emoji} **{title}** - {location}\n"
        text += f"   Status: {status.title()}\n"
        text += f"   Applied: {applied_at[:10]}\n\n"

    await update.message.reply_text(text, parse_mode='Markdown')


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show help information"""
    help_text = """
🤖 **Jobs Bot Help**

**Available Commands:**
• `/start` - Start the bot and see main menu

**Main Features:**
📝 **Create/Update Profile** - Set up your professional information
💼 **View Jobs** - Browse available job positions and apply
📋 **My Applications** - Check status of your applications
ℹ️ **Help** - Show this help message

**How to Apply for Jobs:**
1. First, create your profile with your professional information
2. Browse available jobs using 'View Jobs'
3. Click on any job to see details
4. Apply with one click using your saved profile

**Need Support?**
Contact the admin if you have any issues or questions.
    """

    await update.message.reply_text(help_text, parse_mode='Markdown')


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel conversation"""
    await update.message.reply_text(
        "❌ Operation cancelled. Use the menu buttons to continue.",
        reply_markup=ReplyKeyboardMarkup([
            [KeyboardButton("📝 Create/Update Profile")],
            [KeyboardButton("💼 View Jobs"), KeyboardButton("📋 My Applications")],
            [KeyboardButton("ℹ️ Help")]
        ], resize_keyboard=True)
    )
    return ConversationHandler.END


def main():
    """Start the bot"""
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()

    # Profile creation conversation handler
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

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(profile_conv_handler)
    application.add_handler(MessageHandler(filters.TEXT, button_handler))
    application.add_handler(CallbackQueryHandler(job_callback))

    # Start the bot
    print("🤖 Jobs Bot is starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()