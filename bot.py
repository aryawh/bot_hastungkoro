import logging
import os
import re
from datetime import datetime
import pytz
import pandas as pd
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext

# Load environment variables from .env file
load_dotenv()

# Get the bot token from environment variable
BOT_TOKEN = os.getenv('BOT_TOKEN')

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

# Check if BOT_TOKEN is set
if not BOT_TOKEN:
    logger.error('BOT_TOKEN is not set. Please set it in the .env file.')
    raise ValueError('BOT_TOKEN is not set. Please set it in the .env file.')

logger.info('BOT_TOKEN is set')

# Dictionary to store weights and logs for each user
user_data = {}
total_eggs = 0  # Variable to store the total eggs
last_reset_date = datetime.now(pytz.timezone('Asia/Jakarta')).strftime('%Y-%m')  # Track the last reset date (year and month)

# Timezone for Jakarta
jakarta_tz = pytz.timezone('Asia/Jakarta')

# Regex pattern to extract egg count
egg_pattern = re.compile(r'(\d+)\s*butir\s*telur\s*ikan', re.IGNORECASE)

def reset_data_if_needed():
    global user_data, total_eggs, last_reset_date
    current_month = datetime.now(jakarta_tz).strftime('%Y-%m')
    if current_month != last_reset_date:
        user_data = {}
        total_eggs = 0
        last_reset_date = current_month
        logger.info("Data reset for the new month")

# Define a few command handlers. These usually take the two arguments update and context.
async def start(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /start is issued."""
    reset_data_if_needed()
    await update.message.reply_text(
        'Hai! Kirim pesan dengan jumlah telur ikan dalam butir, ex: "Saya panen 10000 butir telur ikan" dan saya akan mencatatnya. Gunakan /report untuk melihat laporan.'
    )

async def help_command(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /help is issued."""
    reset_data_if_needed()
    await update.message.reply_text('Help! Perintah yang tersedia: /start, /help, /report, /export')

async def count_eggs(update: Update, context: CallbackContext) -> None:
    """Extract egg count from the user's message and update the total."""
    reset_data_if_needed()
    global total_eggs

    user_id = update.message.from_user.id
    message_text = update.message.text

    # Extract egg count using regex
    match = egg_pattern.search(message_text)
    if match:
        eggs = int(match.group(1))
        date = datetime.now(jakarta_tz).strftime('%Y-%m-%d %H:%M:%S')

        # Store the egg count and log in the dictionary
        if user_id not in user_data:
            user_data[user_id] = {'total_eggs': 0, 'logs': []}
        
        user_data[user_id]['total_eggs'] += eggs
        user_data[user_id]['logs'].append({'date': date, 'eggs': eggs})

        total_eggs += eggs

        await update.message.reply_text(f'Terima kasih! Anda telah melaporkan {eggs} butir telur ikan.')

async def report(update: Update, context: CallbackContext) -> None:
    """Send a report of today's egg counts for all users."""
    reset_data_if_needed()
    today = datetime.now(jakarta_tz).strftime('%Y-%m-%d')
    report_message = "Laporan jumlah telur ikan hari ini:\n"
    total_eggs_today = 0
    entry_number = 1
    for user_id, data in user_data.items():
        user = await context.bot.get_chat(user_id)
        user_name = user.username if user.username else user.first_name
        for log in data['logs']:
            if log['date'].startswith(today):
                report_message += f"{entry_number}. @{user_name}: {log['eggs']} butir telur ikan pada {log['date']}\n"
                total_eggs_today += log['eggs']
                entry_number += 1
    
    report_message += f"\nTotal hari ini: {total_eggs_today} butir telur ikan"
    await update.message.reply_text(report_message)

async def export(update: Update, context: CallbackContext) -> None:
    """Export the report of egg counts to an Excel file, separated by date in different sheets."""
    reset_data_if_needed()
    # Dictionary to hold data per date
    datewise_data = {}
    total_eggs = 0
    daily_totals = []

    # Organize data by date
    for user_id, data_dict in user_data.items():
        user = await context.bot.get_chat(user_id)
        user_name = user.username if user.username else user.first_name
        for log in data_dict['logs']:
            date = log['date'].split(' ')[0]  # Extract the date part
            if date not in datewise_data:
                datewise_data[date] = []
            datewise_data[date].append([user_name, log['date'], log['eggs']])
    
    # Create an Excel writer object
    file_path = "egg_report.xlsx"
    writer = pd.ExcelWriter(file_path, engine='xlsxwriter')

    # Write each date's data to a separate sheet
    for date, data in datewise_data.items():
        df = pd.DataFrame(data, columns=["Username", "Date", "Eggs"])
        # Calculate the total eggs for this date
        total_eggs_for_date = df['Eggs'].sum()
        daily_totals.append([date, total_eggs_for_date])
        # Append the total row
        total_row = pd.DataFrame([["Total", "", total_eggs_for_date]], columns=df.columns)
        df = pd.concat([df, total_row], ignore_index=True)
        # Write to the sheet
        df.to_excel(writer, sheet_name=date, index=False)
        total_eggs += total_eggs_for_date

    # Write the total sheet
    df_total = pd.DataFrame(daily_totals, columns=["Date", "Total Eggs"])
    df_total = pd.concat([df_total, pd.DataFrame([["Grand Total", total_eggs]], columns=df_total.columns)], ignore_index=True)
    df_total.to_excel(writer, sheet_name="Total", index=False)

    # Close the Excel writer and save the file
    writer.close()

    # Send the Excel file to the user
    await update.message.reply_document(document=open(file_path, 'rb'), filename="egg_report.xlsx")

def main() -> None:
    """Start the bot."""
    # Check if BOT_TOKEN is set
    if not BOT_TOKEN:
        logger.error('BOT_TOKEN is not set. Please set it in the .env file.')
        raise ValueError('BOT_TOKEN is not set. Please set it in the .env file.')

    logger.info('Starting bot...')

    # Create the Application and pass it your bot's token.
    application = Application.builder().token(BOT_TOKEN).build()

    # on different commands - answer in Telegram
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("report", report))
    application.add_handler(CommandHandler("export", export))  # This is still here but not mentioned in help

    # on noncommand i.e message - count the eggs
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, count_eggs))

    # Start the Bot
    logger.info('Bot is polling...')
    application.run_polling()

if __name__ == '__main__':
    main()
