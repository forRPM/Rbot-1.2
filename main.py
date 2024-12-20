import asyncio
import logging
import os
import json
import re
from datetime import date, timedelta

from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder, InlineKeyboardMarkup
from aiogram.types import CallbackQuery

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


BOT_TOKEN = '7319905822:AAEjclhKB7xNobKvLFBqpAw_OhjlER3CeEk'

FOLDER_ID = '1cYJHXXUIP0W4aYLlM99E975dcZuBOmvD'

CREDENTIALS_FILE = 'credentials.json'

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


SCOPES = ['https://www.googleapis.com/auth/drive.readonly']


def get_drive_service():
    creds = None
    
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
   
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
       
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    try:
        service = build('drive', 'v3', credentials=creds)
        return service
    except Exception as e:
        logging.error(f"Error creating OpenAI Drive service: {e}")
        return None

def get_files_from_drive(service, folder_id):
    try:
        results = service.files().list(
            q=f"'{folder_id}' in parents and trashed=false",
            fields="nextPageToken, files(id, name, mimeType)"
        ).execute()
        items = results.get('files', [])
        return items
    except HttpError as error:
        logging.error(f"An error occurred: {error}")
        return None


def build_inline_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="Получить сегодняшнее расписание", callback_data="today")
    builder.button(text="Получить завтрашнее расписание", callback_data="tomorrow")
    builder.button(text="Получить послезавтрашнее расписание", callback_data="after_tomorrow")
    builder.adjust(1)  
    return builder.as_markup()


def get_current_date_number():
    return date.today().day

def extract_date_from_filename(filename):
    match = re.search(r'(\d+)', filename)
    if match:
        return int(match.group(1))
    return None



@dp.message(CommandStart())
async def start_command(message: types.Message):
    await message.answer("Привет! Выбери, какое расписание ты хочешь получить.", reply_markup=build_inline_keyboard())

@dp.callback_query(lambda c: c.data in ["today", "tomorrow", "after_tomorrow"])
async def send_schedule(callback_query: CallbackQuery):
    await bot.answer_callback_query(callback_query.id)  

    service = get_drive_service()
    if not service:
        await callback_query.message.answer("Произошла ошибка при подключении к OpenAI Drive.")
        return
    files = get_files_from_drive(service, FOLDER_ID)
    if not files:
        await callback_query.message.answer("В папке нет файлов или произошла ошибка.")
        return

    current_day_number = get_current_date_number()
    if callback_query.data == "today":
        schedule_days = [current_day_number]
    elif callback_query.data == "tomorrow":
        schedule_days = [current_day_number + 1]
    else:
        schedule_days = [current_day_number + 2]

    for file in files:
        try:
            file_id = file['id']
            file_name = file['name']
            file_mime_type = file['mimeType']

            if file_mime_type == 'application/vnd.google-apps.folder':
                
                continue

            file_day_number = extract_date_from_filename(file_name)

            if file_day_number is None or file_day_number not in schedule_days:
                continue
            
            
            file_data = service.files().get_media(fileId=file_id).execute()
            
            if file_mime_type.startswith('image/'):
                  await bot.send_photo(chat_id=callback_query.message.chat.id, photo=types.BufferedInputFile(file_data, filename=file_name))
            elif file_mime_type == 'application/pdf':
                  await bot.send_document(chat_id=callback_query.message.chat.id, document=types.BufferedInputFile(file_data, filename=file_name))
            else:
                  await bot.send_document(chat_id=callback_query.message.chat.id, document=types.BufferedInputFile(file_data, filename=file_name))


        except HttpError as e:
            logging.error(f"An error occurred while fetching file '{file_name}': {e}")
            await callback_query.message.answer(f"Не удалось получить файл '{file_name}'.")

    await callback_query.message.answer("Расписание отправлено.")


async def main():
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == '__main__':
    import google_auth_oauthlib.flow
    asyncio.run(main())