import logging
import os
import json
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

# Список администраторов с именами для отображения
ADMINS = {
    8004182708: {"name": "Алексей", "username": "alexey_support"},
    7725062904: {"name": "Мария", "username": "maria_help"}
}

QUESTIONS_FILE = "questions.json"

class QuestionBot:
    def __init__(self):
        self.questions = self.load_questions()
    
    def load_questions(self):
        if os.path.exists(QUESTIONS_FILE):
            with open(QUESTIONS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def save_questions(self):
        with open(QUESTIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.questions, f, ensure_ascii=False, indent=2)
    
    def add_question(self, question_id, user_id, username, question_text, admin_id):
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

question_bot = QuestionBot()

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    keyboard = [
        [InlineKeyboardButton("📝 Задать вопрос", callback_data="choose_admin")],
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

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    data = query.data
    
    if data == "choose_admin":
        await show_admin_choice(query)
    
    elif data == "ask_question":
        context.user_data['awaiting_question'] = True
        await query.edit_message_text(
            "📝 Задайте ваш вопрос:\n\n"
            "Пожалуйста, опишите вашу проблему максимально подробно. "
            "Администратор свяжется с вами в ближайшее время."
        )
    
    elif data == "help":
        await help_callback(query)
    
    elif data == "back_to_start":
        keyboard = [
            [InlineKeyboardButton("📝 Задать вопрос", callback_data="choose_admin")],
            [InlineKeyboardButton("ℹ️ Помощь", callback_data="help")]
        ]
        await query.edit_message_text(
            f"Привет, {user.first_name}! 👋\n\n"
            "Я бот для связи с администраторами.",
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
            f"💼 Должность: Администратор\n\n"
            "📝 Теперь напишите ваш вопрос:\n\n"
            "Опишите вашу проблему максимально подробно, чтобы администратор мог лучше помочь вам."
        )
    
    elif data.startswith("answer_"):
        question_id = data.split("_")[1]
        context.user_data['answering_question'] = question_id
        await query.edit_message_text(
            f"💬 Введите ответ на вопрос #{question_id}:"
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
        f"💡 Каждый администратор специализируется на разных вопросах. "
        f"Выберите того, кто лучше всего подходит для решения вашей проблемы.",
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
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_start")]
    ]
    
    await query.edit_message_text(
        help_text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message_text = update.message.text
    
    if context.user_data.get('awaiting_question') and context.user_data.get('selected_admin'):
        context.user_data['awaiting_question'] = False
        admin_id = context.user_data['selected_admin']
        
        question_id = str(len(question_bot.questions) + 1).zfill(3)
        
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
            f"📝 Ваш вопрос: {message_text}\n\n"
            f"Администратор уведомлен и ответит вам в ближайшее время."
        )
        
        # Отправляем уведомление выбранному администратору
        await notify_admin(update, context, question_id, user, message_text, admin_id)
        
        # Очищаем выбранного администратора
        context.user_data.pop('selected_admin', None)
        
    elif context.user_data.get('answering_question'):
        question_id = context.user_data['answering_question']
        admin_response = message_text
        
        if question_id in question_bot.questions:
            question_data = question_bot.questions[question_id]
            
            # Обновляем статус вопроса
            question_data['status'] = 'answered'
            question_data['answer'] = admin_response
            question_bot.save_questions()
            
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
                await update.message.reply_text(f"❌ Не удалось отправить ответ пользователю: {e}")
            
            context.user_data.pop('answering_question', None)
    
    else:
        # Если просто текст - предлагаем выбрать администратора
        keyboard = [[InlineKeyboardButton("📝 Выбрать администратора", callback_data="choose_admin")]]
        await update.message.reply_text(
            "Напишите ваш вопрос, выбрав администратора из списка!",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def notify_admin(update: Update, context: ContextTypes.DEFAULT_TYPE, question_id: str, user, question_text: str, admin_id: int):
    """Уведомление конкретного администратора"""
    
    keyboard = [[InlineKeyboardButton("📝 Ответить", callback_data=f"answer_{question_id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message_text = (
        f"🆕 НОВЫЙ ВОПРОС #{question_id}\n\n"
        f"👤 От пользователя: {user.first_name}\n"
        f"📱 Username: @{user.username or 'нет'}\n"
        f"🆔 ID: {user.id}\n\n"
        f"📝 Вопрос:\n{question_text}\n\n"
        f"⏰ Время: {datetime.now().strftime('%H:%M %d.%m.%Y')}"
    )
    
    try:
        logging.info(f"📤 Отправка уведомления администратору {admin_id}")
        await context.bot.send_message(
            chat_id=admin_id,
            text=message_text,
            reply_markup=reply_markup
        )
        logging.info(f"✅ Уведомление отправлено администратору {admin_id}")
        
    except Exception as e:
        logging.error(f"❌ Ошибка отправки администратору {admin_id}: {e}")

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id not in ADMINS:
        await update.message.reply_text("❌ У вас нет прав администратора.")
        return
    
    # Вопросы, адресованные этому администратору
    admin_questions = [q for q in question_bot.questions.values() if q['admin_id'] == user_id]
    total_questions = len(admin_questions)
    new_questions = len([q for q in admin_questions if q['status'] == 'new'])
    answered_questions = len([q for q in admin_questions if q['status'] == 'answered'])
    
    admin_info = ADMINS[user_id]
    
    stats_text = (
        f"📊 Панель администратора ({admin_info['name']})\n\n"
        f"Всего ваших вопросов: {total_questions}\n"
        f"Новых: {new_questions}\n"
        f"Отвеченных: {answered_questions}"
    )
    
    await update.message.reply_text(stats_text)

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id not in ADMINS:
        await update.message.reply_text("❌ У вас нет прав администратора.")
        return
    
    total = len(question_bot.questions)
    new = len([q for q in question_bot.questions.values() if q['status'] == 'new'])
    answered = len([q for q in question_bot.questions.values() if q['status'] == 'answered'])
    
    stats_text = (
        f"📈 Общая статистика\n\n"
        f"Всего вопросов: {total}\n"
        f"Ожидают ответа: {new}\n"
        f"Отвечено: {answered}\n"
        f"Процент ответов: {answered/max(total,1)*100:.1f}%"
    )
    
    await update.message.reply_text(stats_text)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ошибок"""
    error = context.error
    logging.error(f"Ошибка в боте: {error}")

def main():
    print("=" * 50)
    print("🤖 БОТ ДЛЯ СВЯЗИ С АДМИНИСТРАТОРАМИ")
    print("=" * 50)
    print("✅ Токен бота: Установлен")
    print("✅ Администраторы:")
    for admin_id, admin_info in ADMINS.items():
        print(f"   - {admin_info['name']} (@{admin_info['username']}) - ID: {admin_id}")
    print("=" * 50)
    
    try:
        application = Application.builder().token(BOT_TOKEN).build()
        
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("admin", admin_command))
        application.add_handler(CommandHandler("stats", stats_command))
        application.add_handler(CallbackQueryHandler(button_handler))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        application.add_error_handler(error_handler)
        
        print("Бот запускается...")
        
        application.run_polling(
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES
        )
        
    except Exception as e:
        logging.error(f"Критическая ошибка: {e}")

if __name__ == '__main__':
    main()
