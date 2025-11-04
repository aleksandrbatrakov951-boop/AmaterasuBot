import logging
import os
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Конфигурация
BOT_TOKEN = "8315624829:AAFy9oynE5bC12uX4cDkDdyRRwYVB5Hryn4"

# ОБНОВЛЕННЫЕ данные администраторов с дополнительной информацией
ADMINS = {
    8004182708: {
        "name": "Пряник", 
        "username": "Deluse_SC",
        "specialization": "Общие вопросы и консультации",
        "description": "Консультирую по общим вопросам и помогаю с организационными моментами"
    },
    7725062904: {
        "name": "Нефи", 
        "username": "voidNameFame",
        "specialization": "Технические вопросы и поддержка",
        "description": "Помогаю с техническими проблемами, настройкой и устранением неполадок"
    }
}

QUESTIONS_FILE = "questions.json"

# Время запуска бота для отслеживания аптайма
START_TIME = time.time()

# Health Check сервер для Render.com
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'Bot is running')
    
    def log_message(self, format, *args):
        return

def run_health_check():
    port = int(os.environ.get('PORT', 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    print(f"✅ Health check server running on port {port}")
    server.serve_forever()

class QuestionBot:
    def __init__(self):
        self.questions = {}
        self.load_questions()
    
    def load_questions(self):
        """Загружает вопросы из файла"""
        try:
            if os.path.exists(QUESTIONS_FILE):
                with open(QUESTIONS_FILE, 'r', encoding='utf-8') as f:
                    self.questions = json.load(f)
                    print(f"✅ Загружено {len(self.questions)} вопросов")
            else:
                self.questions = {}
                print("✅ Файл вопросов создан заново")
        except Exception as e:
            print(f"❌ Ошибка загрузки вопросов: {e}")
            self.questions = {}
    
    def save_questions(self):
        """Сохраняет вопросы в файл"""
        try:
            with open(QUESTIONS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.questions, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"❌ Ошибка сохранения вопросов: {e}")
    
    def add_question(self, question_id, user_id, username, question_text, admin_id):
        """Добавляет новый вопрос"""
        self.questions[question_id] = {
            'user_id': user_id,
            'username': username,
            'question': question_text,
            'admin_id': admin_id,
            'status': 'new',
            'answer': None,
            'timestamp': datetime.now().isoformat()
        }
        self.save_questions()
        print(f"✅ Добавлен вопрос #{question_id} для админа {admin_id}")
    
    def update_question_status(self, question_id, status, answer=None):
        """Обновляет статус вопроса"""
        if question_id in self.questions:
            self.questions[question_id]['status'] = status
            if answer:
                self.questions[question_id]['answer'] = answer
            self.save_questions()
            print(f"✅ Вопрос #{question_id} обновлен: {status}")

# Создаем экземпляр бота
question_bot = QuestionBot()

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    keyboard = [
        [InlineKeyboardButton("📝 Задать вопрос", callback_data="choose_admin")],
        [InlineKeyboardButton("👥 Администраторы", callback_data="show_admins")],
        [InlineKeyboardButton("ℹ️ Помощь", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"Привет, {user.first_name}! 👋\n\n"
        "Я бот для связи с администраторами.\n"
        "Вы можете задать вопрос конкретному администратору.",
        reply_markup=reply_markup
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    help_text = (
        "🤖 Помощь по боту\n\n"
        "📝 Задать вопрос:\n"
        "• Выберите администратора из списка\n"
        "• Напишите ваш вопрос\n"
        "• Администратор ответит вам\n\n"
        "👨‍💼 Наши администраторы:\n"
    )
    
    # Добавляем список администраторов в помощь
    for admin_id, admin_info in ADMINS.items():
        help_text += f"• {admin_info['name']} (@{admin_info['username']})\n"
    
    help_text += "\n❓ Выберите того, кто лучше разбирается в вашей проблеме!"
    
    await update.message.reply_text(help_text)

async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверка работы бота"""
    user = update.effective_user
    current_time = datetime.now().strftime('%H:%M:%S %d.%m.%Y')
    
    # Считаем время работы
    uptime_seconds = time.time() - START_TIME
    hours = int(uptime_seconds // 3600)
    minutes = int((uptime_seconds % 3600) // 60)
    seconds = int(uptime_seconds % 60)
    uptime = f"{hours}ч {minutes}м {seconds}с"
    
    ping_text = (
        f"🏓 PONG!\n\n"
        f"🤖 Бот работает исправно\n"
        f"👤 Пользователь: {user.first_name}\n"
        f"🆔 ID: {user.id}\n"
        f"⏰ Время сервера: {current_time}\n"
        f"⏱ Аптайм: {uptime}\n"
        f"📊 Вопросов в базе: {len(question_bot.questions)}\n"
        f"✅ Все системы в норме"
    )
    
    await update.message.reply_text(ping_text)

async def reload_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Перезагружает данные бота"""
    user_id = update.effective_user.id
    
    if user_id not in ADMINS:
        await update.message.reply_text("❌ У вас нет прав администратора.")
        return
    
    # Сохраняем текущее состояние
    old_count = len(question_bot.questions)
    
    # Перезагружаем вопросы из файла
    question_bot.load_questions()
    new_count = len(question_bot.questions)
    
    # Очищаем user_data для предотвращения конфликтов
    if update.effective_user.id in context.user_data:
        context.user_data.clear()
    
    await update.message.reply_text(
        f"🔄 Данные бота перезагружены!\n\n"
        f"📊 Вопросов в базе:\n"
        f"• Было: {old_count}\n"
        f"• Стало: {new_count}\n\n"
        f"✅ Все данные загружены заново\n"
        f"🧹 Временный кэш очищен"
    )
    
    print(f"✅ Админ {user_id} выполнил перезагрузку данных")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на кнопки"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "choose_admin":
        await show_admin_choice(query)
    
    elif data == "show_admins":
        await show_admins_info(query)
    
    elif data == "help":
        await help_callback(query)
    
    elif data == "back_to_start":
        keyboard = [
            [InlineKeyboardButton("📝 Задать вопрос", callback_data="choose_admin")],
            [InlineKeyboardButton("👥 Администраторы", callback_data="show_admins")],
            [InlineKeyboardButton("ℹ️ Помощь", callback_data="help")]
        ]
        await query.edit_message_text(
            "Главное меню:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif data.startswith("admin_"):
        # Пользователь выбрал администратора
        admin_id = int(data.split("_")[1])
        context.user_data['selected_admin'] = admin_id
        context.user_data['awaiting_question'] = True
        
        admin_info = ADMINS[admin_id]
        await query.edit_message_text(
            f"👤 Вы выбрали: {admin_info['name']}\n"
            f"📧 Юзернейм: @{admin_info['username']}\n\n"
            "📝 Теперь напишите ваш вопрос:\n\n"
            "Опишите вашу проблему максимально подробно, чтобы администратор мог лучше помочь вам."
        )
    
    elif data.startswith("admininfo_"):
        # Показывает подробную информацию об администраторе
        admin_id = int(data.split("_")[1])
        await show_admin_details(query, admin_id)
    
    elif data.startswith("answer_"):
        question_id = data.split("_")[1]
        context.user_data['answering_question'] = question_id
        
        question = question_bot.questions.get(question_id)
        if question:
            await query.edit_message_text(
                f"💬 Вопрос #{question_id}:\n\n"
                f"{question['question']}\n\n"
                f"✍️ Введите ваш ответ:"
            )
        else:
            await query.edit_message_text("❌ Вопрос не найден!")

async def show_admins_info(query):
    """Показывает информацию обо всех администраторах"""
    keyboard = []
    
    # Создаем кнопки для просмотра информации о каждом администраторе
    for admin_id, admin_info in ADMINS.items():
        button_text = f"👤 {admin_info['name']}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"admininfo_{admin_id}")])
    
    # Добавляем кнопки действий
    keyboard.append([InlineKeyboardButton("📝 Задать вопрос", callback_data="choose_admin")])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back_to_start")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "👥 Наши администраторы:\n\n"
        "Здесь вы можете узнать подробнее о каждом администраторе и его специализации.\n"
        "Выберите администратора для просмотра подробной информации:",
        reply_markup=reply_markup
    )

async def show_admin_details(query, admin_id):
    """Показывает подробную информацию об администраторе"""
    admin_info = ADMINS[admin_id]
    
    # Создаем информационное сообщение
    info_text = (
        f"👤 {admin_info['name']}\n"
        f"📧 @{admin_info['username']}\n\n"
        f"🎯 Специализация:\n"
        f"{admin_info['specialization']}\n\n"
        f"📝 О себе:\n"
        f"{admin_info['description']}\n\n"
        f"💡 Вы можете задать вопрос этому администратору, если ваша проблема соответствует его специализации."
    )
    
    keyboard = [
        [InlineKeyboardButton("📝 Задать вопрос этому администратору", callback_data=f"admin_{admin_id}")],
        [InlineKeyboardButton("👥 Все администраторы", callback_data="show_admins")],
        [InlineKeyboardButton("🔙 Главное меню", callback_data="back_to_start")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        info_text,
        reply_markup=reply_markup
    )

async def show_admin_choice(query):
    """Показывает выбор администраторов"""
    keyboard = []
    
    # Создаем кнопки для каждого администратора
    for admin_id, admin_info in ADMINS.items():
        button_text = f"👤 {admin_info['name']} (@{admin_info['username']})"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"admin_{admin_id}")])
    
    # Добавляем кнопку назад
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back_to_start")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    admin_list = "\n".join([f"• {info['name']} (@{info['username']})" for info in ADMINS.values()])
    
    await query.edit_message_text(
        f"👥 Выберите администратора:\n\n"
        f"{admin_list}\n\n"
        f"💡 Выберите администратора, который лучше всего подходит для решения вашей проблемы.",
        reply_markup=reply_markup
    )

async def help_callback(query):
    """Показывает помощь в inline режиме"""
    help_text = (
        "🤖 Как пользоваться ботом:\n\n"
        "1. Нажмите 'Задать вопрос'\n"
        "2. Выберите администратора из списка\n"
        "3. Напишите ваш вопрос\n"
        "4. Ожидайте ответа\n\n"
        "👨‍💼 Наши администраторы:\n"
    )
    
    for admin_id, admin_info in ADMINS.items():
        help_text += f"• {admin_info['name']} (@{admin_info['username']})\n"
    
    keyboard = [
        [InlineKeyboardButton("📝 Задать вопрос", callback_data="choose_admin")],
        [InlineKeyboardButton("👥 Администраторы", callback_data="show_admins")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_start")]
    ]
    
    await query.edit_message_text(
        help_text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    user = update.effective_user
    message_text = update.message.text
    
    print(f"📨 Получено сообщение от {user.id}: {message_text[:50]}...")
    
    # Пользователь задает вопрос выбранному администратору
    if context.user_data.get('awaiting_question') and context.user_data.get('selected_admin'):
        context.user_data['awaiting_question'] = False
        admin_id = context.user_data['selected_admin']
        
        # Генерируем уникальный ID вопроса
        question_id = str(len(question_bot.questions) + 1).zfill(3)
        while question_id in question_bot.questions:
            question_id = str(int(question_id) + 1).zfill(3)
        
        question_bot.add_question(
            question_id=question_id,
            user_id=user.id,
            username=user.username or user.first_name,
            question_text=message_text,
            admin_id=admin_id
        )
        
        admin_info = ADMINS[admin_id]
        
        await update.message.reply_text(
            f"✅ Вопрос #{question_id} принят!\n\n"
            f"👤 Администратор: {admin_info['name']}\n"
            f"📧 Юзернейм: @{admin_info['username']}\n\n"
            f"Администратор уведомлен и ответит вам в ближайшее время."
        )
        
        # Отправляем уведомление администратору
        await notify_admin(update, context, question_id, user, message_text, admin_id)
        
        # Очищаем данные
        context.user_data.pop('selected_admin', None)
        
    # Администратор отвечает на вопрос
    elif context.user_data.get('answering_question'):
        question_id = context.user_data['answering_question']
        admin_response = message_text
        
        if question_id in question_bot.questions:
            question_data = question_bot.questions[question_id]
            
            # Обновляем статус вопроса
            question_bot.update_question_status(
                question_id=question_id,
                status='answered',
                answer=admin_response
            )
            
            try:
                # Отправляем ответ пользователю
                await context.bot.send_message(
                    chat_id=question_data['user_id'],
                    text=f"💌 Ответ на ваш вопрос #{question_id}:\n\n"
                         f"{admin_response}\n\n"
                         f"С уважением, администратор"
                )
                await update.message.reply_text("✅ Ответ отправлен пользователю!")
            except Exception as e:
                await update.message.reply_text(f"❌ Не удалось отправить ответ: {e}")
            
            context.user_data.pop('answering_question', None)
        else:
            await update.message.reply_text("❌ Вопрос не найден!")
            context.user_data.pop('answering_question', None)
    
    else:
        # Если просто текст - предлагаем выбрать администратора
        keyboard = [
            [InlineKeyboardButton("📝 Выбрать администратора", callback_data="choose_admin")],
            [InlineKeyboardButton("👥 Информация об администраторах", callback_data="show_admins")]
        ]
        await update.message.reply_text(
            "Чтобы задать вопрос, выберите администратора из списка:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def notify_admin(update: Update, context: ContextTypes.DEFAULT_TYPE, question_id: str, user, question_text: str, admin_id: int):
    """Уведомляет администратора о новом вопросе"""
    
    keyboard = [[InlineKeyboardButton("📝 Ответить", callback_data=f"answer_{question_id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message_text = (
        f"🆕 НОВЫЙ ВОПРОС #{question_id}\n\n"
        f"👤 От: {user.first_name}\n"
        f"📱 @{user.username or 'без username'}\n"
        f"🆔 ID: {user.id}\n\n"
        f"📝 Вопрос:\n{question_text}\n\n"
        f"⏰ {datetime.now().strftime('%H:%M %d.%m.%Y')}"
    )
    
    try:
        await context.bot.send_message(
            chat_id=admin_id,
            text=message_text,
            reply_markup=reply_markup
        )
        print(f"✅ Уведомление отправлено админу {admin_id}")
    except Exception as e:
        print(f"❌ Ошибка отправки админу {admin_id}: {e}")

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для администраторов"""
    user_id = update.effective_user.id
    
    if user_id not in ADMINS:
        await update.message.reply_text("❌ У вас нет прав администратора.")
        return
    
    # Считаем вопросы для этого администратора
    admin_questions = [q for q in question_bot.questions.values() if q['admin_id'] == user_id]
    total = len(admin_questions)
    new = len([q for q in admin_questions if q['status'] == 'new'])
    answered = len([q for q in admin_questions if q['status'] == 'answered'])
    
    admin_info = ADMINS[user_id]
    
    stats_text = (
        f"📊 Статистика ({admin_info['name']})\n\n"
        f"Всего вопросов: {total}\n"
        f"📨 Новых: {new}\n"
        f"✅ Отвеченных: {answered}"
    )
    
    await update.message.reply_text(stats_text)

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Общая статистика"""
    user_id = update.effective_user.id
    
    if user_id not in ADMINS:
        await update.message.reply_text("❌ У вас нет прав администратора.")
        return
    
    total = len(question_bot.questions)
    new = len([q for q in question_bot.questions.values() if q['status'] == 'new'])
    answered = len([q for q in question_bot.questions.values() if q['status'] == 'answered'])
    
    percentage = (answered / max(total, 1)) * 100
    
    stats_text = (
        f"📈 Общая статистика\n\n"
        f"Всего вопросов: {total}\n"
        f"📨 Ожидают ответа: {new}\n"
        f"✅ Отвечено: {answered}\n"
        f"📊 Процент ответов: {percentage:.1f}%"
    )
    
    await update.message.reply_text(stats_text)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ошибок"""
    error = context.error
    logging.error(f"Ошибка: {error}")

def main():
    """Основная функция запуска бота"""
    print("=" * 60)
    print("🤖 БОТ ДЛЯ СВЯЗИ С АДМИНИСТРАТОРАМИ")
    print("=" * 60)
    print("✅ Токен бота: Установлен")
    print("✅ Администраторы:")
    for admin_id, admin_info in ADMINS.items():
        print(f"   👤 {admin_info['name']} (@{admin_info['username']}) - ID: {admin_id}")
    print(f"✅ Загружено вопросов: {len(question_bot.questions)}")
    print("=" * 60)
    
    # Запускаем health check сервер
    health_thread = threading.Thread(target=run_health_check, daemon=True)
    health_thread.start()
    print("✅ Health check server запущен")
    
    try:
        # Создаем приложение
        application = Application.builder().token(BOT_TOKEN).build()
        
        # Добавляем обработчики
        handlers = [
            CommandHandler("start", start_command),
            CommandHandler("help", help_command),
            CommandHandler("admin", admin_command),
            CommandHandler("stats", stats_command),
            CommandHandler("ping", ping_command),
            CommandHandler("reload", reload_command),  # Добавлена команда reload
            CallbackQueryHandler(button_handler),
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
        ]
        
        for handler in handlers:
            application.add_handler(handler)
        
        application.add_error_handler(error_handler)
        
        print("🔄 Запускаем бота...")
        
        # Запускаем бота
        application.run_polling(
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES
        )
        
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        logging.error(f"Критическая ошибка: {e}")

if __name__ == '__main__':
    main()
