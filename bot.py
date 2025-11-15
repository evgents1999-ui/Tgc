import os
import logging
import json
import csv
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, CallbackQueryHandler

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфигурация
BOT_TOKEN = "8487676074:AAEVzIaYrJlZeoq8DoJKV_YSm4MsKDXyw-w"
ADMIN_ID = 7296765144
ADMIN_USERNAME = "@DL00O0"

# Хранилище данных
files_db = {}
used_keys = set()
user_stats = {}  # Статистика по пользователям
admin_logs = []  # Логи действий админа

# Сохранение и загрузка данных
DATA_FILE = "bot_data.json"

def save_data():
    """Сохранить данные в файл"""
    data = {
        'files_db': files_db,
        'used_keys': list(used_keys),
        'user_stats': user_stats,
        'admin_logs': admin_logs[-1000:]  # Сохраняем последние 1000 логов
    }
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка сохранения данных: {e}")

def load_data():
    """Загрузить данные из файла"""
    global files_db, used_keys, user_stats, admin_logs
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                files_db = data.get('files_db', {})
                used_keys = set(data.get('used_keys', []))
                user_stats = data.get('user_stats', {})
                admin_logs = data.get('admin_logs', [])
    except Exception as e:
        logger.error(f"Ошибка загрузки данных: {e}")

def log_admin_action(action: str, details: str = ""):
    """Логирование действий администратора"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = {
        'timestamp': timestamp,
        'action': action,
        'details': details
    }
    admin_logs.append(log_entry)
    save_data()

def generate_key():
    """Генерация уникального ключа"""
    import random
    import string
    
    while True:
        key = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        if key not in files_db and key not in used_keys:
            return key

async def start(update: Update, context: CallbackContext):
    """Обработчик команды /start"""
    user_id = update.effective_user.id
    username = update.effective_user.username or "Без username"
    
    # Обновляем статистику пользователя
    if user_id not in user_stats:
        user_stats[user_id] = {
            'username': username,
            'first_seen': datetime.now().isoformat(),
            'last_seen': datetime.now().isoformat(),
            'files_requested': 0,
            'keys_used': []
        }
    else:
        user_stats[user_id]['last_seen'] = datetime.now().isoformat()
        user_stats[user_id]['username'] = username
    
    save_data()
    
    if user_id == ADMIN_ID:
        keyboard = [
            [InlineKeyboardButton("📊 Статистика", callback_data="stats")],
            [InlineKeyboardButton("📁 Управление файлами", callback_data="file_manage")],
            [InlineKeyboardButton("👥 Пользователи", callback_data="user_manage")],
            [InlineKeyboardButton("⚙️ Настройки", callback_data="system_settings")],
            [InlineKeyboardButton("📋 Логи", callback_data="view_logs")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"👋 Привет, администратор {ADMIN_USERNAME}!\n"
            f"Выберите действие из меню ниже:",
            reply_markup=reply_markup
        )
        log_admin_action("Админ вошел в систему")
    else:
        await update.message.reply_text(
            "👋 Привет! Я бот для обмена файлами.\n\n"
            "Чтобы получить файл, используйте команду:\n"
            "/key КЛЮЧ\n\n"
            "Например: /key ABC12345\n\n"
            "Для помощи: /help"
        )

async def handle_file(update: Update, context: CallbackContext):
    """Обработчик загрузки файлов"""
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ Только администратор может загружать файлы.")
        return
    
    # Определяем тип файла и получаем file_id
    file_info = None
    file_type = "unknown"
    file_name = "Неизвестно"
    
    if update.message.document:
        file_info = update.message.document
        file_type = "document"
        file_name = file_info.file_name or "Документ"
    elif update.message.photo:
        file_info = update.message.photo[-1]
        file_type = "photo"
        file_name = "Фото"
    elif update.message.video:
        file_info = update.message.video
        file_type = "video"
        file_name = file_info.file_name or "Видео"
    elif update.message.audio:
        file_info = update.message.audio
        file_type = "audio"
        file_name = f"{file_info.title or 'Аудио'} - {file_info.performer or 'Неизвестно'}"
    elif update.message.voice:
        file_info = update.message.voice
        file_type = "voice"
        file_name = "Голосовое сообщение"
    elif update.message.video_note:
        file_info = update.message.video_note
        file_type = "video_note"
        file_name = "Видео-заметка"
    elif update.message.sticker:
        file_info = update.message.sticker
        file_type = "sticker"
        file_name = f"Стикер {file_info.emoji or ''}"
    else:
        await update.message.reply_text("❌ Неподдерживаемый тип файла.")
        return
    
    file_id = file_info.file_id
    file_size = getattr(file_info, 'file_size', 0)
    
    # Генерируем ключ
    key = generate_key()
    
    # Сохраняем в базу
    files_db[key] = {
        'file_id': file_id,
        'file_type': file_type,
        'file_name': file_name,
        'file_size': file_size,
        'upload_time': datetime.now().isoformat(),
        'uploader_id': user_id,
        'downloads': 0,
        'last_download': None,
        'is_active': True
    }
    
    save_data()
    log_admin_action("Файл загружен", f"Ключ: {key}, Файл: {file_name}")
    
    keyboard = [
        [InlineKeyboardButton("🔒 Деактивировать ключ", callback_data=f"deactivate_{key}")],
        [InlineKeyboardButton("🗑 Удалить файл", callback_data=f"delete_{key}")],
        [InlineKeyboardButton("📊 Статистика", callback_data="stats")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"✅ Файл успешно загружен!\n\n"
        f"📁 Имя файла: {file_name}\n"
        f"🔑 Ключ: <code>{key}</code>\n"
        f"📊 Тип: {file_type}\n"
        f"📦 Размер: {file_size} байт\n\n"
        f"Для получения файла используйте:\n"
        f"<code>/key {key}</code>",
        parse_mode='HTML',
        reply_markup=reply_markup
    )

async def get_file_by_key(update: Update, context: CallbackContext):
    """Обработчик команды /key"""
    user_id = update.effective_user.id
    username = update.effective_user.username or "Без username"
    
    if not context.args:
        await update.message.reply_text(
            "❌ Использование: /key КЛЮЧ\n\n"
            "Пример: /key ABC12345"
        )
        return
    
    key = context.args[0].upper()
    
    # Обновляем статистику пользователя
    if user_id not in user_stats:
        user_stats[user_id] = {
            'username': username,
            'first_seen': datetime.now().isoformat(),
            'last_seen': datetime.now().isoformat(),
            'files_requested': 0,
            'keys_used': []
        }
    
    user_stats[user_id]['files_requested'] += 1
    user_stats[user_id]['last_seen'] = datetime.now().isoformat()
    user_stats[user_id]['username'] = username
    
    if key in used_keys:
        await update.message.reply_text("❌ Этот ключ уже был использован.")
        user_stats[user_id]['keys_used'].append({
            'key': key,
            'time': datetime.now().isoformat(),
            'status': 'used'
        })
        save_data()
        return
    
    if key not in files_db or not files_db[key].get('is_active', True):
        await update.message.reply_text("❌ Неверный ключ или файл не найден.")
        user_stats[user_id]['keys_used'].append({
            'key': key,
            'time': datetime.now().isoformat(),
            'status': 'invalid'
        })
        save_data()
        return
    
    file_data = files_db[key]
    
    try:
        # Отправляем файл в зависимости от типа
        caption = f"📁 {file_data['file_name']}\n🔑 Ключ: {key}"
        
        if file_data['file_type'] == 'document':
            await update.message.reply_document(
                document=file_data['file_id'],
                caption=caption
            )
        elif file_data['file_type'] == 'photo':
            await update.message.reply_photo(
                photo=file_data['file_id'],
                caption=caption
            )
        elif file_data['file_type'] == 'video':
            await update.message.reply_video(
                video=file_data['file_id'],
                caption=caption
            )
        elif file_data['file_type'] == 'audio':
            await update.message.reply_audio(
                audio=file_data['file_id'],
                caption=caption
            )
        elif file_data['file_type'] == 'voice':
            await update.message.reply_voice(
                voice=file_data['file_id'],
                caption=caption
            )
        elif file_data['file_type'] == 'video_note':
            await update.message.reply_video_note(
                video_note=file_data['file_id']
            )
        elif file_data['file_type'] == 'sticker':
            await update.message.reply_sticker(
                sticker=file_data['file_id']
            )
        
        # Обновляем статистику файла
        files_db[key]['downloads'] += 1
        files_db[key]['last_download'] = datetime.now().isoformat()
        
        user_stats[user_id]['keys_used'].append({
            'key': key,
            'time': datetime.now().isoformat(),
            'status': 'success'
        })
        
        save_data()
        
        # Уведомление админу о скачивании
        if ADMIN_ID:
            try:
                await context.bot.send_message(
                    ADMIN_ID,
                    f"📥 Файл скачан!\n"
                    f"🔑 Ключ: {key}\n"
                    f"👤 Пользователь: {username} (ID: {user_id})\n"
                    f"📁 Файл: {file_data['file_name']}\n"
                    f"📊 Всего скачиваний: {files_db[key]['downloads']}"
                )
            except Exception as e:
                logger.error(f"Ошибка уведомления админу: {e}")
        
        await update.message.reply_text("✅ Файл успешно отправлен!")
        
    except Exception as e:
        logger.error(f"Ошибка отправки файла: {e}")
        await update.message.reply_text("❌ Ошибка при отправке файла.")
        user_stats[user_id]['keys_used'].append({
            'key': key,
            'time': datetime.now().isoformat(),
            'status': 'error'
        })
        save_data()

# ===== РАСШИРЕННЫЕ ФУНКЦИИ АДМИНА =====

async def admin_panel(update: Update, context: CallbackContext):
    """Главная админ-панель"""
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        return
    
    keyboard = [
        [InlineKeyboardButton("📊 Статистика", callback_data="stats")],
        [InlineKeyboardButton("📁 Управление файлами", callback_data="file_manage")],
        [InlineKeyboardButton("👥 Пользователи", callback_data="user_manage")],
        [InlineKeyboardButton("⚙️ Настройки", callback_data="system_settings")],
        [InlineKeyboardButton("📋 Логи", callback_data="view_logs")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "👋 Панель администратора\nВыберите действие:",
        reply_markup=reply_markup
    )

async def file_management(update: Update, context: CallbackContext):
    """Управление файлами"""
    query = update.callback_query
    await query.answer()
    
    total_files = len(files_db)
    active_files = sum(1 for f in files_db.values() if f.get('is_active', True))
    total_downloads = sum(f['downloads'] for f in files_db.values())
    
    keyboard = [
        [InlineKeyboardButton("📋 Список всех файлов", callback_data="list_files")],
        [InlineKeyboardButton("🗑 Удалить все файлы", callback_data="confirm_clear_all")],
        [InlineKeyboardButton("📊 Статистика файлов", callback_data="file_stats")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"📁 Управление файлами\n\n"
        f"📊 Статистика:\n"
        f"• Всего файлов: {total_files}\n"
        f"• Активных файлов: {active_files}\n"
        f"• Неактивных файлов: {total_files - active_files}\n"
        f"• Всего скачиваний: {total_downloads}",
        reply_markup=reply_markup
    )

async def list_all_files(update: Update, context: CallbackContext):
    """Список всех файлов"""
    query = update.callback_query
    await query.answer()
    
    if not files_db:
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="file_manage")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("📁 Файлы не найдены.", reply_markup=reply_markup)
        return
    
    files_text = "📋 Список всех файлов:\n\n"
    for i, (key, file_data) in enumerate(list(files_db.items())[:15], 1):  # Показываем первые 15
        status = "✅" if file_data.get('is_active', True) else "❌"
        files_text += f"{i}. {status} {key} - {file_data['file_name'][:30]}\n"
        files_text += f"   📥 Скачиваний: {file_data['downloads']}\n"
        files_text += f"   📅 Загружен: {file_data['upload_time'][:10]}\n\n"
    
    if len(files_db) > 15:
        files_text += f"\n... и еще {len(files_db) - 15} файлов"
    
    keyboard = [
        [InlineKeyboardButton("🗑 Удалить все", callback_data="confirm_clear_all")],
        [InlineKeyboardButton("📁 Управление", callback_data="file_manage")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(files_text, reply_markup=reply_markup)

async def user_management(update: Update, context: CallbackContext):
    """Управление пользователями"""
    query = update.callback_query
    await query.answer()
    
    total_users = len(user_stats)
    active_today = sum(1 for u in user_stats.values() 
                      if datetime.fromisoformat(u['last_seen']).date() == datetime.now().date())
    
    keyboard = [
        [InlineKeyboardButton("👥 Список пользователей", callback_data="list_users")],
        [InlineKeyboardButton("📊 Статистика пользователей", callback_data="user_stats")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"👥 Управление пользователями\n\n"
        f"📊 Статистика:\n"
        f"• Всего пользователей: {total_users}\n"
        f"• Активных сегодня: {active_today}",
        reply_markup=reply_markup
    )

async def list_users(update: Update, context: CallbackContext):
    """Список пользователей"""
    query = update.callback_query
    await query.answer()
    
    if not user_stats:
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="user_manage")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("👥 Пользователи не найдены.", reply_markup=reply_markup)
        return
    
    users_text = "👥 Список пользователей:\n\n"
    for i, (user_id, user_data) in enumerate(list(user_stats.items())[:10], 1):
        last_seen = datetime.fromisoformat(user_data['last_seen']).strftime("%d.%m.%Y %H:%M")
        users_text += f"{i}. 👤 {user_data['username']}\n"
        users_text += f"   🆔 ID: {user_id}\n"
        users_text += f"   📥 Запросов: {user_data['files_requested']}\n"
        users_text += f"   🕒 Последняя активность: {last_seen}\n\n"
    
    if len(user_stats) > 10:
        users_text += f"\n... и еще {len(user_stats) - 10} пользователей"
    
    keyboard = [
        [InlineKeyboardButton("👥 Управление", callback_data="user_manage")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(users_text, reply_markup=reply_markup)

async def system_settings(update: Update, context: CallbackContext):
    """Настройки системы"""
    query = update.callback_query
    await query.answer()
    
    total_size = sum(f.get('file_size', 0) for f in files_db.values())
    
    keyboard = [
        [InlineKeyboardButton("🗑 Очистить все данные", callback_data="confirm_clear_all")],
        [InlineKeyboardButton("📤 Экспорт данных", callback_data="export_data")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"⚙️ Настройки системы\n\n"
        f"💾 Использование памяти:\n"
        f"• Файлов: {len(files_db)}\n"
        f"• Общий размер: {total_size} байт\n"
        f"• Пользователей: {len(user_stats)}\n"
        f"• Записей в логах: {len(admin_logs)}",
        reply_markup=reply_markup
    )

async def view_logs(update: Update, context: CallbackContext):
    """Просмотр логов"""
    query = update.callback_query
    await query.answer()
    
    if not admin_logs:
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("📋 Логи отсутствуют.", reply_markup=reply_markup)
        return
    
    logs_text = "📋 Последние 10 действий:\n\n"
    for log in admin_logs[-10:]:
        logs_text += f"🕒 {log['timestamp']}\n"
        logs_text += f"📝 {log['action']}\n"
        if log['details']:
            logs_text += f"📄 {log['details'][:50]}\n"
        logs_text += "\n"
    
    keyboard = [
        [InlineKeyboardButton("🗑 Очистить логи", callback_data="clear_logs")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(logs_text, reply_markup=reply_markup)

async def export_data(update: Update, context: CallbackContext):
    """Экспорт данных"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("📊 Экспорт статистики", callback_data="export_stats")],
        [InlineKeyboardButton("📁 Экспорт списка файлов", callback_data="export_files")],
        [InlineKeyboardButton("👥 Экспорт пользователей", callback_data="export_users")],
        [InlineKeyboardButton("🔙 Назад", callback_data="system_settings")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "📤 Экспорт данных\nВыберите что экспортировать:",
        reply_markup=reply_markup
    )

async def show_stats(update: Update, context: CallbackContext):
    """Показать расширенную статистику"""
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        message = query.message
    else:
        message = update.message
    
    total_files = len(files_db)
    active_files = sum(1 for f in files_db.values() if f.get('is_active', True))
    total_downloads = sum(f['downloads'] for f in files_db.values())
    total_users = len(user_stats)
    
    # Статистика за последние 7 дней
    week_ago = datetime.now() - timedelta(days=7)
    recent_downloads = sum(
        f['downloads'] for f in files_db.values() 
        if f.get('last_download') and datetime.fromisoformat(f['last_download']) > week_ago
    )
    
    stats_text = (
        f"📊 Расширенная статистика\n\n"
        f"📁 Файлы:\n"
        f"• Всего: {total_files}\n"
        f"• Активных: {active_files}\n"
        f"• Неактивных: {total_files - active_files}\n"
        f"• Всего скачиваний: {total_downloads}\n"
        f"• Скачиваний за неделю: {recent_downloads}\n\n"
        f"👥 Пользователи:\n"
        f"• Всего: {total_users}\n"
        f"• Активных сегодня: {sum(1 for u in user_stats.values() if datetime.fromisoformat(u['last_seen']).date() == datetime.now().date())}\n\n"
        f"💾 Система:\n"
        f"• Использованных ключей: {len(used_keys)}\n"
        f"• Записей в логах: {len(admin_logs)}"
    )
    
    keyboard = [
        [InlineKeyboardButton("📁 Управление файлами", callback_data="file_manage")],
        [InlineKeyboardButton("👥 Пользователи", callback_data="user_manage")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await query.edit_message_text(stats_text, reply_markup=reply_markup)
    else:
        await message.reply_text(stats_text, reply_markup=reply_markup)

# ===== ОБРАБОТЧИКИ КНОПОК =====

async def button_handler(update: Update, context: CallbackContext):
    """Главный обработчик нажатий на кнопки"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if user_id != ADMIN_ID:
        await query.message.reply_text("❌ Доступно только администратору.")
        return
    
    data = query.data
    
    # Основное меню
    if data == "stats":
        await show_stats(update, context)
    elif data == "file_manage":
        await file_management(update, context)
    elif data == "user_manage":
        await user_management(update, context)
    elif data == "system_settings":
        await system_settings(update, context)
    elif data == "view_logs":
        await view_logs(update, context)
    elif data == "back_to_main":
        await admin_panel_callback(update, context)
    
    # Управление файлами
    elif data == "list_files":
        await list_all_files(update, context)
    elif data == "file_stats":
        await show_stats(update, context)
    elif data == "confirm_clear_all":
        await confirm_clear_all(update, context)
    
    # Пользователи
    elif data == "list_users":
        await list_users(update, context)
    elif data == "user_stats":
        await show_stats(update, context)
    
    # Настройки
    elif data == "export_data":
        await export_data(update, context)
    
    # Логи
    elif data == "clear_logs":
        await clear_logs(update, context)
    
    # Операции с файлами
    elif data.startswith("deactivate_"):
        key = data.replace("deactivate_", "")
        await deactivate_file(update, context, key)
    elif data.startswith("delete_"):
        key = data.replace("delete_", "")
        await delete_file(update, context, key)

async def admin_panel_callback(update: Update, context: CallbackContext):
    """Обработчик возврата в главное меню"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("📊 Статистика", callback_data="stats")],
        [InlineKeyboardButton("📁 Управление файлами", callback_data="file_manage")],
        [InlineKeyboardButton("👥 Пользователи", callback_data="user_manage")],
        [InlineKeyboardButton("⚙️ Настройки", callback_data="system_settings")],
        [InlineKeyboardButton("📋 Логи", callback_data="view_logs")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "👋 Панель администратора\nВыберите действие:",
        reply_markup=reply_markup
    )

async def deactivate_file(update: Update, context: CallbackContext, key: str):
    """Деактивировать файл"""
    query = update.callback_query
    await query.answer()
    
    if key in files_db:
        files_db[key]['is_active'] = False
        save_data()
        log_admin_action("Файл деактивирован", f"Ключ: {key}")
        
        keyboard = [[InlineKeyboardButton("🔙 Назад к файлам", callback_data="list_files")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"✅ Файл с ключом {key} деактивирован.",
            reply_markup=reply_markup
        )
    else:
        await query.edit_message_text("❌ Файл не найден.")

async def delete_file(update: Update, context: CallbackContext, key: str):
    """Удалить файл"""
    query = update.callback_query
    await query.answer()
    
    if key in files_db:
        file_name = files_db[key]['file_name']
        del files_db[key]
        used_keys.add(key)
        save_data()
        log_admin_action("Файл удален", f"Ключ: {key}, Имя: {file_name}")
        
        keyboard = [[InlineKeyboardButton("🔙 Назад к файлам", callback_data="list_files")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"✅ Файл '{file_name}' с ключом {key} удален.",
            reply_markup=reply_markup
        )
    else:
        await query.edit_message_text("❌ Файл не найден.")

async def confirm_clear_all(update: Update, context: CallbackContext):
    """Подтверждение очистки всех файлов"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("✅ Да, удалить все", callback_data="clear_all_confirmed")],
        [InlineKeyboardButton("❌ Отмена", callback_data="file_manage")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "⚠️ Вы уверены что хотите удалить ВСЕ файлы?\n"
        "Это действие нельзя отменить!",
        reply_markup=reply_markup
    )

async def clear_all_confirmed(update: Update, context: CallbackContext):
    """Очистка всех файлов после подтверждения"""
    query = update.callback_query
    await query.answer()
    
    count = len(files_db)
    files_db.clear()
    used_keys.clear()
    save_data()
    log_admin_action("Все файлы удалены", f"Удалено файлов: {count}")
    
    keyboard = [[InlineKeyboardButton("🔙 В главное меню", callback_data="back_to_main")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"✅ Все файлы ({count}) успешно удалены!",
        reply_markup=reply_markup
    )

async def clear_logs(update: Update, context: CallbackContext):
    """Очистка логов"""
    query = update.callback_query
    await query.answer()
    
    count = len(admin_logs)
    admin_logs.clear()
    save_data()
    log_admin_action("Логи очищены", f"Удалено записей: {count}")
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="view_logs")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"✅ Логи ({count} записей) успешно очищены!",
        reply_markup=reply_markup
    )

# Добавляем обработчики для новых callback данных
async def extended_button_handler(update: Update, context: CallbackContext):
    """Расширенный обработчик кнопок"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if user_id != ADMIN_ID:
        return
    
    data = query.data
    
    if data == "clear_all_confirmed":
        await clear_all_confirmed(update, context)

def main():
    """Основная функция"""
    # Загружаем данные при старте
    load_data()
    
    # Создаем приложение
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Добавляем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stats", show_stats))
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CommandHandler("key", get_file_by_key))
    application.add_handler(CommandHandler("help", start))
    
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_file))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(CallbackQueryHandler(extended_button_handler))
    
    # Запускаем бота
    print("Бот запущен...")
    print(f"Админ: {ADMIN_USERNAME} (ID: {ADMIN_ID})")
    application.run_polling()

if __name__ == '__main__':
    main()
