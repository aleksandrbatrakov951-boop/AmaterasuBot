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
ADMIN_IDS = [8004182708, 7725062904]
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
    
    def add_question(self, question_id, user_id, username, question_text):
        self.questions[question_id] = {
            'user_id': user_id,
            'username': username,
            'question': question_text,
            'status': 'new',
            'admin_id': None,
            'answer': None,
            'timestamp': datetime.now().isoformat()
        }
        self.save_questions()
    
    def update_question_status(self, question_id, status, admin_id=None, answer=None):
        if question_id in self.questions:
            self.questions[question_id]['status'] = status
            if admin_id:
                self.questions[question_id]['admin_id'] = admin_id
            if answer:
                self.questions[question_id]['answer'] = answer
            self.save_questions()

question_bot = QuestionBot()

def escape_text(text):
    """Экранирует все специальные символы Markdown"""
    if not text:
        return text
    escape_chars = '_*[]()~`>#+-=|{}.!'
    for char in escape_chars:
        text = text.replace(char, f'\\{char}')
    return text

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    keyboard = [
        [InlineKeyboardButton("📝 Задать вопрос", callback_data="ask_question")],
        [InlineKeyboardButton("ℹ️ Помощь", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"Привет, {user.first_name}! 👋\n\n"
        "Я бот для связи с администраторами.\n"
        "Вы можете задать вопрос, и администраторы получат уведомление.",
        reply_markup=reply_markup
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "🤖 Помощь по боту\n\n"
        "📝 Задать вопрос:\n"
        "Используйте кнопку 'Задать вопрос' или просто напишите свой вопрос боту\n\n"
        "❓ Частые вопросы:\n"
        "• Вопросы обрабатываются в порядке очереди\n"
        "• Администраторы ответят вам в личные сообщения\n"
        "• Пожалуйста, формулируйте вопросы четко и вежливо"
    )
    await update.message.reply_text(help_text)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    data = query.data
    
    if data == "ask_question":
        context.user_data['awaiting_question'] = True
        await query.edit_message_text(
            "📝 Задайте ваш вопрос:\n\n"
            "Пожалуйста, опишите вашу проблему или вопрос максимально подробно. "
            "Администратор свяжется с вами в ближайшее время."
        )
    
    elif data == "help":
        await query.edit_message_text(
            "🤖 Как пользоваться ботом:\n\n"
            "1. Нажмите 'Задать вопрос'\n"
            "2. Напишите ваш вопрос\n"
            "3. Ожидайте ответа администратора",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📝 Задать вопрос", callback_data="ask_question")],
                [InlineKeyboardButton("🔙 Назад", callback_data="back_to_start")]
            ])
        )
    
    elif data == "back_to_start":
        keyboard = [
            [InlineKeyboardButton("📝 Задать вопрос", callback_data="ask_question")],
            [InlineKeyboardButton("ℹ️ Помощь", callback_data="help")]
        ]
        await query.edit_message_text(
            f"Привет, {user.first_name}! 👋\n\n"
            "Я бот для связи с администраторами.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif data.startswith("answer_"):
        question_id = data.split("_")[1]
        context.user_data['answering_question'] = question_id
        await query.edit_message_text(
            f"💬 Введите ответ на вопрос #{question_id}:"
        )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message_text = update.message.text
    
    if context.user_data.get('awaiting_question'):
        context.user_data['awaiting_question'] = False
        
        question_id = str(len(question_bot.questions) + 1).zfill(3)
        
        question_bot.add_question(
            question_id=question_id,
            user_id=user.id,
            username=user.username or user.first_name,
            question_text=message_text
        )
        
        await update.message.reply_text(
            f"✅ Вопрос #{question_id} принят!\n\n"
            f"Ваш вопрос: {message_text}\n\n"
            "Администраторы уведомлены и ответят вам в ближайшее время."
        )
        
        await notify_admins(update, context, question_id, user, message_text)
        
    elif context.user_data.get('answering_question'):
        question_id = context.user_data['answering_question']
        admin_response = message_text
        
        if question_id in question_bot.questions:
            question_data = question_bot.questions[question_id]
            
            question_bot.update_question_status(
                question_id=question_id,
                status='answered',
                admin_id=user.id,
                answer=admin_response
            )
            
            try:
                await context.bot.send_message(
                    chat_id=question_data['user_id'],
                    text=f"💌 Ответ на ваш вопрос #{question_id}:\n\n"
                         f"{admin_response}\n\n"
                         f"Ответ от администратора"
                )
                await update.message.reply_text("✅ Ответ отправлен пользователю!")
            except Exception as e:
                await update.message.reply_text(f"❌ Не удалось отправить ответ пользователю: {e}")
            
            context.user_data.pop('answering_question', None)
    
    else:
        keyboard = [[InlineKeyboardButton("📝 Задать вопрос", callback_data="ask_question")]]
        await update.message.reply_text(
            "Напишите ваш вопрос, и я передам его администраторам!",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def notify_admins(update: Update, context: ContextTypes.DEFAULT_TYPE, question_id: str, user, question_text: str):
    keyboard = [
        [InlineKeyboardButton("📝 Ответить", callback_data=f"answer_{question_id}")]
    ]
    
    # Экранируем весь текст
    safe_username = escape_text(user.username or 'нет')
    safe_question = escape_text(question_text)
    safe_first_name = escape_text(user.first_name)
    
    message_text = (
        f"🆕 НОВЫЙ ВОПРОС #{question_id}\n\n"
        f"👤 ПОЛЬЗОВАТЕЛЬ: {safe_first_name}\n"
        f"📱 USERNAME: @{safe_username}\n"
        f"🆔 ID: {user.id}\n\n"
        f"📝 ВОПРОС:\n{safe_question}\n\n"
        f"⏰ Время: {datetime.now().strftime('%H:%M %d.%m.%Y')}"
    )
    
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=message_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='MarkdownV2'  # Используем MarkdownV2 с экранированием
            )
        except Exception as e:
            logging.error(f"Не удалось уведомить администратора {admin_id}: {e}")

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ У вас нет прав администратора.")
        return
    
    total_questions = len(question_bot.questions)
    new_questions = len([q for q in question_bot.questions.values() if q['status'] == 'new'])
    answered_questions = len([q for q in question_bot.questions.values() if q['status'] == 'answered'])
    
    stats_text = (
        f"📊 Панель администратора\n\n"
        f"• Всего вопросов: {total_questions}\n"
        f"• Новых: {new_questions}\n"
        f"• Отвеченных: {answered_questions}"
    )
    
    await update.message.reply_text(stats_text)

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ У вас нет прав администратора.")
        return
    
    total = len(question_bot.questions)
    new = len([q for q in question_bot.questions.values() if q['status'] == 'new'])
    answered = len([q for q in question_bot.questions.values() if q['status'] == 'answered'])
    
    stats_text = (
        f"📈 Статистика вопросов\n\n"
        f"• Всего: {total}\n"
        f"• Ожидают ответа: {new}\n"
        f"• Отвечено: {answered}\n"
        f"• Процент ответов: {answered/max(total,1)*100:.1f}%"
    )
    
    await update.message.reply_text(stats_text)

def main():
    print("=" * 50)
    print("🤖 БОТ ДЛЯ СВЯЗИ С АДМИНИСТРАТОРАМИ")
    print("=" * 50)
    print("✅ Токен бота: Установлен")
    print(f"✅ Администраторы: {len(ADMIN_IDS)} пользователя")
    print("=" * 50)
    print("Бот запускается...")
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    application.run_polling()

if __name__ == '__main__':
    main()
