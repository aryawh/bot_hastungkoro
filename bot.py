import logging
import os
import re
from datetime import datetime
import pytz
import pandas as pd
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, ConversationHandler

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

# Dictionary to store weights and logs for each user and group
user_data = {}
group_data = {}
total_eggs = 0  # Variable to store the total eggs
last_reset_date = datetime.now(pytz.timezone('Asia/Jakarta')).strftime('%Y-%m')  # Track the last reset date (year and month)

# Timezone for Jakarta
jakarta_tz = pytz.timezone('Asia/Jakarta')

# Regex pattern to extract egg count
egg_pattern = re.compile(r'(\d+)\s*butir', re.IGNORECASE)

# Conversation states
GROUP_CHOICE = 0

def reset_data_if_needed():
    global user_data, group_data, total_eggs, last_reset_date
    current_month = datetime.now(jakarta_tz).strftime('%Y-%m')
    if current_month != last_reset_date:
        user_data = {}
        group_data = {}
        total_eggs = 0
        last_reset_date = current_month
        logger.info("Data reset for the new month")

# Define a few command handlers. These usually take the two arguments update and context.
async def start(update: Update, context: CallbackContext) -> int:
    """Send a message when the command /start is issued, and ask the user to select their group."""
    reset_data_if_needed()

    reply_keyboard = [['Samawa Fish', 'Karya Mina Rahayu']]
    await update.message.reply_text(
        'Silakan pilih kelompok tani Anda:',
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)
    )

    return GROUP_CHOICE

async def group_choice(update: Update, context: CallbackContext) -> int:
    """Handle group selection and confirm to the user."""
    group = update.message.text
    user_id = update.message.from_user.id

    # Store the user's group
    context.user_data['group'] = group

    # Initialize data for the group if not already done
    if group not in group_data:
        group_data[group] = {}

    # Initialize user data within the selected group
    if user_id not in group_data[group]:
        group_data[group][user_id] = {'total_eggs': 0, 'logs': []}

    await update.message.reply_text(
        f"Anda telah bergabung dengan kelompok tani '{group}'. Silakan laporkan jumlah telur, misalnya: '1500 butir'."
    )

    return ConversationHandler.END

async def help_command(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /help is issued."""
    reset_data_if_needed()
    
    help_text = (
        "Perintah yang tersedia:\n"
        "1. /start - Memulai bot dan memilih kelompok tani.\n"
        "2. /help - Menampilkan daftar perintah yang tersedia dan penjelasannya.\n"
        "3. /report - Menampilkan laporan jumlah telur ikan hari ini berdasarkan kelompok tani.\n"
        "Cara menggunakan bot:\n"
        "1. Kirim pesan dengan jumlah telur ikan dalam butir, contoh: '1500 butir'.\n"
        "2. Gunakan perintah /report untuk melihat laporan."
    )
    
    await update.message.reply_text(help_text)

async def count_eggs(update: Update, context: CallbackContext) -> None:
    """Extract egg count from the user's message and update the total."""
    reset_data_if_needed()
    global total_eggs

    user_id = update.message.from_user.id
    group = context.user_data.get('group')
    if not group:
        await update.message.reply_text('Silakan pilih kelompok tani dengan perintah /start.')
        return

    message_text = update.message.text

    # Extract egg count using regex
    match = egg_pattern.search(message_text)
    if match:
        eggs = int(match.group(1))
        date = datetime.now(jakarta_tz).strftime('%Y-%m-%d %H:%M:%S')

        # Store the egg count and log in the dictionary for the group
        group_data[group][user_id]['total_eggs'] += eggs
        group_data[group][user_id]['logs'].append({'date': date, 'eggs': eggs})

        total_eggs += eggs

        await update.message.reply_text(f'Terima kasih! Anda telah melaporkan {eggs} butir telur ikan.')

async def report(update: Update, context: CallbackContext) -> None:
    """Send a report of today's egg counts for all users in the selected group."""
    reset_data_if_needed()
    group = context.user_data.get('group')
    if not group:
        await update.message.reply_text('Silakan pilih kelompok tani dengan perintah /start.')
        return

    today = datetime.now(jakarta_tz).strftime('%Y-%m-%d')
    report_message = f"Laporan jumlah telur ikan hari ini untuk kelompok '{group}':\n"
    total_eggs_today = 0
    entry_number = 1
    for user_id, data in group_data[group].items():
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
    """Export the report of egg counts to an Excel file, separated by group and user."""
    reset_data_if_needed()
    group = context.user_data.get('group')
    if not group:
        await update.message.reply_text('Silakan pilih kelompok tani dengan perintah /start.')
        return

    # Dictionary to hold data per date and group
    datewise_data = {}
    total_eggs = 0
    daily_totals = []
    user_totals = {}

    # Organize data by date and user
    for user_id, data_dict in group_data[group].items():
        user = await context.bot.get_chat(user_id)
        user_name = user.username if user.username else user.first_name
        user_totals[user_name] = data_dict['total_eggs']
        for log in data_dict['logs']:
            date = log['date'].split(' ')[0]  # Extract the date part
            if date not in datewise_data:
                datewise_data[date] = []
            datewise_data[date].append([user_name, log['date'], log['eggs']])

    # Create an Excel writer object
    file_path = f"{group}_egg_report.xlsx"
    writer = pd.ExcelWriter(file_path, engine='xlsxwriter')

    # Write each date's data to a separate sheet
    for date, data in datewise_data.items():
        df = pd.DataFrame(data, columns=["Username", "Tanggal", "Butir Telur"])
        # Calculate the total eggs for this date
        total_eggs_for_date = df['Butir Telur'].sum()
        daily_totals.append([date, total_eggs_for_date])
        # Append the total row
        total_row = pd.DataFrame([["Total", "", total_eggs_for_date]], columns=df.columns)
        df = pd.concat([df, total_row], ignore_index=True)
        # Write to the sheet
        df.to_excel(writer, sheet_name=date, index=False)
        total_eggs += total_eggs_for_date

    # Write the total sheet
    df_total = pd.DataFrame(daily_totals, columns=["Tanggal", "Total Butir Telur"])
    df_total = pd.concat([df_total, pd.DataFrame([["Grand Total", total_eggs]], columns=df_total.columns)], ignore_index=True)
    df_total.to_excel(writer, sheet_name="Total", index=False)

    # Write the user totals sheet
    df_user_totals = pd.DataFrame(user_totals.items(), columns=["Username", "Total Butir Telur"])
    df_user_totals.to_excel(writer, sheet_name="User Totals", index=False)

    # Close the Excel writer and save the file
    writer.close()

    # Send the Excel file to the user
    await update.message.reply_document(document=open(file_path, 'rb'), filename=f"{group}_laporan_telur_ikan.xlsx")

def main() -> None:
    """Start the bot."""
    # Check if BOT_TOKEN is set
    if not BOT_TOKEN:
        logger.error('BOT_TOKEN is not set. Please set it in the .env file.')
        raise ValueError('BOT_TOKEN is not set. Please set it in the .env file.')

    logger.info('Starting bot...')

    # Create the Application and pass it your bot's token.
    application = Application.builder().token(BOT_TOKEN).build()

    # Define the conversation handler for choosing the group
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            GROUP_CHOICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, group_choice)],
        },
        fallbacks=[CommandHandler("start", start)],
    )

    # Add the conversation handler and other command handlers
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("report", report))
    application.add_handler(CommandHandler("export", export))

    # on noncommand i.e message - count the eggs
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, count_eggs))

    # Start the Bot
    logger.info('Bot is polling...')
    application.run_polling()

if __name__ == '__main__':
    main()

