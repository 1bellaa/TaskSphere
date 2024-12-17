import os
import pandas as pd
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from telegram import Update, Bot, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application, ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
)
from database import (
    create_list, delete_list, add_task, delete_task, update_task_status, get_tasks, list_all_lists
)

# Scheduler for reminders
scheduler = BackgroundScheduler()
scheduler.start()

# Token
TOKEN = os.getenv("TOKEN")

if not TOKEN:
    raise ValueError("Error: Telegram Bot Token not found.")

application = Application.builder().token(TOKEN).build()

# Constants
EXCEL_FILE = "completed_tasks.xlsx"
STATUS_OPTIONS = ["In Progress", "VE For Checking", "Execs For Checking", "Done"]

# Excel file
if not os.path.exists(EXCEL_FILE):
    df = pd.DataFrame(columns=["Task Name", "List", "Assigned To", "Deadline", "Completion Time", "Status"])
    df.to_excel(EXCEL_FILE, index=False)

# Store the task being updated
TASK_BEING_UPDATED = {}

# Command: Start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Welcome to the Task Sphere! Use /help for a list of commands.")

# Command: Help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Commands:\n"
        "Create a new task list:\n"
        "/create_list <list_name>\n"
        "Show all lists\n"
        "/show_lists"
        "Delete a list\n"
        "/delete_list <list_name>\n"
        "Add a task\n"
        "Deadline format: MM/DD/YYYY HH:MM AM/PM\n"
        "/add_task <list_name> <task_name>\n <@username(s)>\n <deadline>\n"
        "Delete a task\n"
        "/delete_task <list_name> <task_name>\n"
        "Update task status\n"
        "/update_task <task_name>\n"
        "Show all tasks in a list\n"
        "/show_tasks <list_name>\n"
        "Show tasks assigned to a specific staffer\n"
        "/show_tasks @username"
    )

# Command: Create List
async def create_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    list_name = " ".join(context.args)
    if not list_name:
        await update.message.reply_text("Usage: /create_list <list_name>")
        return
    if create_list(list_name):
        await update.message.reply_text(f"List '{list_name}' created successfully.")
    else:
        await update.message.reply_text(f"List '{list_name}' already exists.")

# Command: Show Lists
async def show_lists_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lists = list_all_lists() 

    if not lists:
        await update.message.reply_text("No task lists found.")  # If no lists exist
    else:
        response = "Lists:\n" + "\n".join(f"- {list_name}" for list_name in lists)
        await update.message.reply_text(response)

# Command: Show Tasks
async def show_tasks_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    list_name = " ".join(context.args)
    tasks = get_tasks(list_name=list_name)

    if not tasks:
        await update.message.reply_text(f"No tasks found in list '{list_name}'.")
        return

    response = "Active Tasks:\n"
    for idx, task in enumerate(tasks, start=1):
        response += (
            f"[{idx}]\n"
            f"List: {task['List']}\n"
            f"Task: {task['Task Name']}\n"
            f"Assigned To: {task['Assigned To']}\n"
            f"Deadline: {task['Deadline'].strftime('%B %d, %Y, %I:%M %p')}\n"
            f"Status: {task['Status']}\n\n"
        )
    await update.message.reply_text(response)

# Command: Delete Task
async def delete_task_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /delete_task <list_name> <task_name>")
        return

    list_name = context.args[0]
    task_name = " ".join(context.args[1:])

    if delete_task(list_name, task_name):
        await update.message.reply_text(f"Task '{task_name}' deleted successfully from list '{list_name}'.")
    else:
        await update.message.reply_text(f"Task '{task_name}' not found in list '{list_name}'.")

# Command: Delete List
async def delete_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    list_name = " ".join(context.args)
    if not list_name:
        await update.message.reply_text("Usage: /delete_list <list_name>")
        return
    if delete_list(list_name):
        await update.message.reply_text(f"List '{list_name}' deleted successfully.")
    else:
        await update.message.reply_text(f"List '{list_name}' not found.")

# Command: Add Task
async def add_task_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 3:
        await update.message.reply_text("Usage: /add_task <list_name> <task_name> <@username(s)> <deadline>")
        return

    list_name = context.args[0]
    task_name = context.args[1]
    assigned_to = " ".join([arg for arg in context.args[2:] if arg.startswith("@")])  # Multiple usernames
    deadline_input = " ".join(arg for arg in context.args[3:] if not arg.startswith("@"))  # Deadline

    try:
        deadline_dt = datetime.strptime(deadline_input, "%m/%d/%Y %I:%M %p") if deadline_input else datetime.now().replace(hour=23, minute=59)
        if deadline_dt <= datetime.now():
            await update.message.reply_text("Deadline must be in the future.")
            return
    except ValueError:
        await update.message.reply_text("Invalid deadline format. Use MM/DD/YYYY HH:MM AM/PM.")
        return

    result = add_task(list_name, task_name, assigned_to, deadline_dt)
    if result == "ListNotFound":
        await update.message.reply_text(f"List '{list_name}' not found. Please create it first.")
    else:
        await update.message.reply_text(f"Task '{task_name}' added successfully, assigned to: {assigned_to}.")

# Command: Update Task
async def update_task_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global TASK_BEING_UPDATED
    task_name = " ".join(context.args)
    if not task_name:
        await update.message.reply_text("Usage: /update_task <task_name>")
        return

    TASK_BEING_UPDATED[update.effective_user.id] = task_name
    keyboard = [[KeyboardButton(status)] for status in STATUS_OPTIONS]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    await update.message.reply_text("Choose the new status for the task:", reply_markup=reply_markup)

# Handler: Update Task Status
async def handle_status_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global TASK_BEING_UPDATED
    user_id = update.effective_user.id
    new_status = update.message.text

    if user_id not in TASK_BEING_UPDATED or new_status not in STATUS_OPTIONS:
        await update.message.reply_text("Invalid action or status.")
        return

    task_name = TASK_BEING_UPDATED.pop(user_id)
    if update_task_status(task_name, new_status):
        await update.message.reply_text(f"Task '{task_name}' updated to '{new_status}'.")

        # Save completed task to Excel if status is "Done"
        if new_status.lower() == "done":
            save_completed_task_to_excel(task_name)
    else:
        await update.message.reply_text(f"Failed to update task '{task_name}'.")

# Save to Excel
def save_completed_task_to_excel(task_name):
    completed_tasks = get_tasks()
    for task in completed_tasks:
        if task["Task Name"] == task_name and task["Status"].lower() == "done":
            df = pd.read_excel(EXCEL_FILE)
            new_row = {
                "Task Name": task["Task Name"],
                "List": task["List"],
                "Assigned To": task["Assigned To"],  # Supports multiple users
                "Deadline": task["Deadline"],
                "Completion Time": task["Completion Time"],
                "Status": "Done"
            }
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            df.to_excel(EXCEL_FILE, index=False)
            break

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("create_list", create_list_command))
    app.add_handler(CommandHandler("show_lists", show_tasks_command))
    app.add_handler(CommandHandler("delete_task", delete_task_command))
    app.add_handler(CommandHandler("delete_list", delete_list_command))
    app.add_handler(CommandHandler("add_task", add_task_command))
    app.add_handler(CommandHandler("show_tasks", show_tasks_command))
    app.add_handler(CommandHandler("update_task", update_task_command))

    # Message Handler for Status Update
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_status_update))

    app.run_polling()

if __name__ == "__main__":
    main()
