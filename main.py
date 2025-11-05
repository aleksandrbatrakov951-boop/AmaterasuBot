import logging
import os
import json
import threading
import time
import random
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime, timedelta
from collections import defaultdict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Конфигурация
BOT_TOKEN = os.environ.get('BOT_TOKEN', "8315624829:AAFy9oynE5bC12uX4cDkDdyRRwYVB5Hryn4")

# Данные администраторов
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
REVIEWS_FILE = "reviews.json"

# Время запуска бота
START_TIME = time.time()

# Защита от спама
class RateLimiter:
    def __init__(self):
        self.user_requests = defaultdict(list)
    
    def is_limited(self, user_id, limit=5, period=60):
        """Проверяет лимит запросов для пользователя"""
        now = datetime.now()
        # Очищаем старые запросы
        self.user_requests[user_id] = [t for t in self.user_requests[user_id] 
                                     if now - t < timedelta(seconds=period)]
        
        if len(self.user_requests[user_id]) >= limit:
            return True
        
        self.user_requests[user_id].append(now)
        return False

rate_limiter = RateLimiter()

# Health Check сервер
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
    logging.info(f"Health check server running on port {port}")
    server.serve_forever()

def create_bar(percentage, max_percentage=100):
    """Создает текстовый график-прогрессбар"""
    bars = 10
    filled = int((percentage / max_percentage) * bars)
    empty = bars - filled
    return "▰" * filled + "▱" * empty

def create_emoji_bar(percentage):
    """Создает прогрессбар из эмодзи"""
    bars = 5
    filled = int((percentage / 100) * bars)
    return "●" * filled + "○" * (bars - filled)

def create_progress_circle(percentage):
    """Создает круговой индикатор прогресса"""
    circles = ["⚪", "🔴", "🟠", "🟡", "🟢", "🔵", "🟣"]
    index = min(int(percentage / 15), len(circles) - 1)
    return circles[index]

def create_small_bar(percentage):
    """Создает маленький прогрессбар"""
    bars = 5
    filled = int((percentage / 100) * bars)
    return "█" * filled + "░" * (bars - filled)

def validate_question_text(text):
    """Проверяет валидность текста вопроса"""
    if not text or len(text.strip()) < 10:
        return False, "❌ Вопрос слишком короткий. Минимум 10 символов."
    if len(text) > 2000:
        return False, "❌ Вопрос слишком длинный. Максимум 2000 символов."
    return True, ""

def generate_unique_question_id():
    """Генерирует уникальный ID вопроса"""
    timestamp = int(time.time())
    random_suffix = random.randint(1000, 9999)
    return f"{timestamp}_{random_suffix}"

def log_admin_action(admin_id, action, target=None):
    """Логирует действия администраторов"""
    admin_name = ADMINS.get(admin_id, {}).get('name', 'Unknown')
    logging.info(f"ADMIN_ACTION: {admin_name} ({admin_id}) - {action} - {target}")

class ReviewSystem:
    def __init__(self):
        self.reviews = {}
        self.load_reviews()
    
    def load_reviews(self):
        """Загружает отзывы из файла"""
        try:
            if os.path.exists(REVIEWS_FILE):
                with open(REVIEWS_FILE, 'r', encoding='utf-8') as f:
                    self.reviews = json.load(f)
                    logging.info(f"Loaded reviews for {len(self.reviews)} admins")
            else:
                self.reviews = {}
        except Exception as e:
            logging.error(f"Error loading reviews: {e}")
            self.reviews = {}
    
    def save_reviews(self):
        """Сохраняет отзывы в файл"""
        try:
            with open(REVIEWS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.reviews, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.error(f"Error saving reviews: {e}")
    
    def add_review(self, admin_id, stars, review_text, user_id, username):
        """Добавляет новый отзыв"""
        if str(admin_id) not in self.reviews:
            self.reviews[str(admin_id)] = {
                'ratings': [],
                'reviews': [],
                'average_rating': 0
            }
        
        review_data = {
            'stars': stars,
            'text': review_text,
            'user_id': user_id,
            'username': username,
            'timestamp': datetime.now().isoformat()
        }
        
        self.reviews[str(admin_id)]['ratings'].append(stars)
        if review_text:
            self.reviews[str(admin_id)]['reviews'].append(review_data)
        
        ratings = self.reviews[str(admin_id)]['ratings']
        self.reviews[str(admin_id)]['average_rating'] = sum(ratings) / len(ratings)
        
        self.save_reviews()
        logging.info(f"Added review for admin {admin_id}: {stars} stars")
    
    def get_admin_stats(self, admin_id):
        """Возвращает статистику отзывов для администратора"""
        admin_key = str(admin_id)
        if admin_key not in self.reviews:
            return {
                'average_rating': 0,
                'total_ratings': 0,
                'total_reviews': 0,
                'rating_distribution': {1:0, 2:0, 3:0, 4:0, 5:0}
            }
        
        admin_data = self.reviews[admin_key]
        ratings = admin_data['ratings']
        
        distribution = {1:0, 2:0, 3:0, 4:0, 5:0}
        for rating in ratings:
            distribution[rating] += 1
        
        return {
            'average_rating': admin_data['average_rating'],
            'total_ratings': len(ratings),
            'total_reviews': len(admin_data['reviews']),
            'rating_distribution': distribution
        }
    
    def get_rating_stars(self, rating):
        """Создает строку со звездами рейтинга"""
        full_star = "⭐"
        empty_star = "☆"
        stars = ""
        for i in range(1, 6):
            if i <= rating:
                stars += full_star
            else:
                stars += empty_star
        return stars

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
                    logging.info(f"Loaded {len(self.questions)} questions")
            else:
                self.questions = {}
        except Exception as e:
            logging.error(f"Error loading questions: {e}")
            self.questions = {}
    
    def save_questions(self):
        """Сохраняет вопросы в файл"""
        try:
            with open(QUESTIONS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.questions, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.error(f"Error saving questions: {e}")
    
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
        logging.info(f"Added question #{question_id} for admin {admin_id}")
    
    def update_question_status(self, question_id, status, answer=None):
        """Обновляет статус вопроса"""
        if question_id in self.questions:
            self.questions[question_id]['status'] = status
            if answer:
                self.questions[question_id]['answer'] = answer
            self.save_questions()
            logging.info(f"Question #{question_id} updated: {status}")

    def get_user_recent_questions(self, user_id, hours=24):
        """Получает recent вопросы пользователя"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        return [q for q in self.questions.values() 
                if q['user_id'] == user_id and 
                datetime.fromisoformat(q['timestamp']) > cutoff_time]

# Создаем экземпляры бота и системы отзывов
question_bot = QuestionBot()
review_system = ReviewSystem()

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    
    # Проверка лимита запросов
    if rate_limiter.is_limited(user.id):
        await update.message.reply_text("❌ Слишком много запросов. Подождите минуту.")
        return
    
    keyboard = [
        [InlineKeyboardButton("📝 Задать вопрос", callback_data="choose_admin")],
        [InlineKeyboardButton("👥 Администраторы", callback_data="show_admins")],
        [InlineKeyboardButton("⭐ Рейтинги", callback_data="show_ratings")],
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
        "⭐ Система отзывов:\n"
        "• После ответа вы можете оценить помощь\n"
        "• Поставьте от 1 до 5 звезд\n"
        "• Оставьте текстовый отзыв (по желанию)\n\n"
        "👨‍💼 Наши администраторы:\n"
    )
    
    for admin_id, admin_info in ADMINS.items():
        stats = review_system.get_admin_stats(admin_id)
        rating_text = f" ({stats['average_rating']:.1f}⭐)" if stats['total_ratings'] > 0 else ""
        help_text += f"• {admin_info['name']} (@{admin_info['username']}){rating_text}\n"
    
    help_text += "\n❓ Выберите того, кто лучше разбирается в вашей проблеме!"
    
    await update.message.reply_text(help_text)

async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверка работы бота"""
    user = update.effective_user
    current_time = datetime.now().strftime('%H:%M:%S %d.%m.%Y')
    
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
        f"⭐ Отзывов в базе: {sum(len(admin_data['reviews']) for admin_data in review_system.reviews.values())}\n"
        f"✅ Все системы в норме"
    )
    
    await update.message.reply_text(ping_text)

async def reload_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Перезагружает данные бота"""
    user_id = update.effective_user.id
    
    if user_id not in ADMINS:
        await update.message.reply_text("❌ У вас нет прав администратора.")
        return
    
    old_count = len(question_bot.questions)
    question_bot.load_questions()
    new_count = len(question_bot.questions)
    review_system.load_reviews()
    
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
    
    log_admin_action(user_id, "reload_data")

async def cleanup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Очистка старых вопросов"""
    user_id = update.effective_user.id
    
    if user_id not in ADMINS:
        await update.message.reply_text("❌ У вас нет прав администратора.")
        return
    
    cutoff_time = datetime.now() - timedelta(days=7)
    old_questions = []
    
    for qid, question in question_bot.questions.items():
        if datetime.fromisoformat(question['timestamp']) < cutoff_time:
            old_questions.append(qid)
    
    for qid in old_questions:
        del question_bot.questions[qid]
    
    question_bot.save_questions()
    await update.message.reply_text(f"🗑️ Удалено {len(old_questions)} старых вопросов")
    log_admin_action(user_id, "cleanup_questions", f"removed {len(old_questions)}")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Общая статистика для всех пользователей"""
    total = len(question_bot.questions)
    new = len([q for q in question_bot.questions.values() if q['status'] == 'new'])
    answered = len([q for q in question_bot.questions.values() if q['status'] == 'answered'])
    
    percentage = (answered / max(total, 1)) * 100
    
    total_bar = create_bar(100, 100)
    answered_bar = create_bar(percentage, 100) if total > 0 else "▰▰▰▰▰▰▰▰▰▰"
    
    admin_stats = []
    for admin_id, admin_info in ADMINS.items():
        admin_questions = [q for q in question_bot.questions.values() if q['admin_id'] == admin_id]
        admin_total = len(admin_questions)
        admin_answered = len([q for q in admin_questions if q['status'] == 'answered'])
        admin_percentage = (admin_answered / max(admin_total, 1)) * 100 if admin_total > 0 else 0
        
        rating_stats = review_system.get_admin_stats(admin_id)
        
        admin_stats.append({
            'name': admin_info['name'],
            'total': admin_total,
            'answered': admin_answered,
            'percentage': admin_percentage,
            'bar': create_bar(admin_percentage, 100) if admin_total > 0 else "▱▱▱▱▱▱▱▱▱▱",
            'rating': rating_stats['average_rating'],
            'total_ratings': rating_stats['total_ratings']
        })
    
    stats_text = (
        f"📊 ОБЩАЯ СТАТИСТИКА БОТА\n\n"
        f"📈 Прогресс выполнения:\n"
        f"{answered_bar} {percentage:.1f}%\n\n"
        f"🔢 Цифры:\n"
        f"• Всего вопросов: {total}\n"
        f"• 📨 Ожидают ответа: {new}\n"
        f"• ✅ Отвечено: {answered}\n\n"
        f"👥 СТАТИСТИКА ПО АДМИНИСТРАТОРАМ:\n"
    )
    
    for admin in admin_stats:
        stats_text += f"\n👤 {admin['name']}:\n"
        stats_text += f"{admin['bar']} {admin['percentage']:.1f}%\n"
        stats_text += f"• Всего: {admin['total']} | Ответов: {admin['answered']}\n"
        if admin['total_ratings'] > 0:
            stats_text += f"• ⭐ Рейтинг: {admin['rating']:.1f}/5 ({admin['total_ratings']} оценок)\n"
    
    stats_text += f"\n⏰ Бот работает исправно ✅"
    
    await update.message.reply_text(stats_text)

async def graph_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Графическая статистика с эмодзи"""
    total = len(question_bot.questions)
    new = len([q for q in question_bot.questions.values() if q['status'] == 'new'])
    answered = len([q for q in question_bot.questions.values() if q['status'] == 'answered'])
    in_progress = total - new - answered
    
    if total > 0:
        new_percent = (new / total) * 100
        answered_percent = (answered / total) * 100
        in_progress_percent = (in_progress / total) * 100
    else:
        new_percent = answered_percent = in_progress_percent = 0
    
    graph_text = (
        f"📊 ГРАФИЧЕСКАЯ СТАТИСТИКА\n\n"
        f"🎯 Статус вопросов:\n"
        f"🟢 Отвечено: {create_emoji_bar(answered_percent)} {answered_percent:.1f}% ({answered})\n"
        f"🟡 В работе: {create_emoji_bar(in_progress_percent)} {in_progress_percent:.1f}% ({in_progress})\n"
        f"🔴 Новые: {create_emoji_bar(new_percent)} {new_percent:.1f}% ({new})\n\n"
        f"📈 Общий прогресс:\n"
        f"{create_progress_circle(answered_percent)} {answered_percent:.1f}% выполнено\n\n"
        f"👥 Администраторы:\n"
    )
    
    for admin_id, admin_info in ADMINS.items():
        admin_questions = [q for q in question_bot.questions.values() if q['admin_id'] == admin_id]
        admin_total = len(admin_questions)
        admin_answered = len([q for q in admin_questions if q['status'] == 'answered'])
        admin_percentage = (admin_answered / max(admin_total, 1)) * 100 if admin_total > 0 else 0
        
        rating_stats = review_system.get_admin_stats(admin_id)
        rating_text = f" ⭐ {rating_stats['average_rating']:.1f}" if rating_stats['total_ratings'] > 0 else ""
        
        graph_text += f"👤 {admin_info['name']}: {create_small_bar(admin_percentage)} {admin_percentage:.0f}% ({admin_answered}/{admin_total}){rating_text}\n"
    
    await update.message.reply_text(graph_text)

async def ratings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает рейтинги всех администраторов"""
    ratings_text = "⭐ РЕЙТИНГИ АДМИНИСТРАТОРОВ\n\n"
    
    for admin_id, admin_info in ADMINS.items():
        stats = review_system.get_admin_stats(admin_id)
        
        ratings_text += f"👤 {admin_info['name']} (@{admin_info['username']})\n"
        
        if stats['total_ratings'] > 0:
            stars = review_system.get_rating_stars(int(round(stats['average_rating'])))
            ratings_text += f"{stars} {stats['average_rating']:.1f}/5\n"
            ratings_text += f"📊 На основе {stats['total_ratings']} оценок\n"
            
            for star in range(5, 0, -1):
                count = stats['rating_distribution'][star]
                percentage = (count / stats['total_ratings']) * 100 if stats['total_ratings'] > 0 else 0
                bar = create_bar(percentage, 100)
                ratings_text += f"{'⭐' * star}{'☆' * (5-star)} {bar} {percentage:.1f}% ({count})\n"
            
            if stats['total_reviews'] > 0:
                ratings_text += f"📝 Отзывов: {stats['total_reviews']}\n"
        else:
            ratings_text += "⭐ Еще нет оценок\n"
        
        ratings_text += "────────────────────\n\n"
    
    keyboard = [[InlineKeyboardButton("🔙 Главное меню", callback_data="back_to_start")]]
    
    await update.message.reply_text(
        ratings_text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для администраторов"""
    user_id = update.effective_user.id
    
    if user_id not in ADMINS:
        await update.message.reply_text("❌ У вас нет прав администратора.")
        return
    
    admin_questions = [q for q in question_bot.questions.values() if q['admin_id'] == user_id]
    total = len(admin_questions)
    new = len([q for q in admin_questions if q['status'] == 'new'])
    answered = len([q for q in admin_questions if q['status'] == 'answered'])
    
    admin_info = ADMINS[user_id]
    rating_stats = review_system.get_admin_stats(user_id)
    
    stats_text = (
        f"📊 Статистика ({admin_info['name']})\n\n"
        f"❓ Вопросы:\n"
        f"• Всего: {total}\n"
        f"• 📨 Новых: {new}\n"
        f"• ✅ Отвеченных: {answered}\n\n"
    )
    
    if rating_stats['total_ratings'] > 0:
        stars = review_system.get_rating_stars(int(round(rating_stats['average_rating'])))
        stats_text += (
            f"⭐ Рейтинги:\n"
            f"• Средний: {stars} {rating_stats['average_rating']:.1f}/5\n"
            f"• Всего оценок: {rating_stats['total_ratings']}\n"
            f"• Текстовых отзывов: {rating_stats['total_reviews']}\n"
        )
    else:
        stats_text += "⭐ Рейтинги: пока нет оценок\n"
    
    await update.message.reply_text(stats_text)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на кнопки"""
    query = update.callback_query
    
    # Проверка на устаревшие callback-и
    if time.time() - query.message.date.timestamp() > 3600:
        await query.edit_message_text("❌ Это меню устарело. Используйте /start")
        return
    
    await query.answer()
    data = query.data
    
    if data == "choose_admin":
        await show_admin_choice(query)
    elif data == "show_admins":
        await show_admins_info(query)
    elif data == "show_ratings":
        await show_ratings_info(query)
    elif data == "help":
        await help_callback(query)
    elif data == "back_to_start":
        keyboard = [
            [InlineKeyboardButton("📝 Задать вопрос", callback_data="choose_admin")],
            [InlineKeyboardButton("👥 Администраторы", callback_data="show_admins")],
            [InlineKeyboardButton("⭐ Рейтинги", callback_data="show_ratings")],
            [InlineKeyboardButton("ℹ️ Помощь", callback_data="help")]
        ]
        await query.edit_message_text(
            "Главное меню:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    elif data.startswith("admin_"):
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
    elif data.startswith("rate_"):
        parts = data.split("_")
        question_id = parts[1]
        stars = int(parts[2])
        
        context.user_data['rated_question'] = question_id
        context.user_data['rating_stars'] = stars
        
        keyboard = [
            [InlineKeyboardButton("✅ Оставить отзыв", callback_data=f"review_{question_id}_{stars}")],
            [InlineKeyboardButton("❌ Пропустить", callback_data=f"skip_review_{question_id}_{stars}")]
        ]
        
        await query.edit_message_text(
            f"Спасибо за оценку {review_system.get_rating_stars(stars)}!\n\n"
            f"📝 Хотите оставить текстовый отзыв?\n"
            f"Это поможет администратору стать лучше!",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    elif data.startswith("review_"):
        parts = data.split("_")
        question_id = parts[1]
        stars = int(parts[2])
        
        context.user_data['awaiting_review'] = True
        context.user_data['review_question'] = question_id
        context.user_data['review_stars'] = stars
        
        await query.edit_message_text(
            f"✍️ Напишите ваш отзыв о помощи администратора:\n\n"
            f"• Что понравилось?\n"
            f"• Что можно улучшить?\n"
            f"• Общие впечатления\n\n"
            f"Отправьте текстовое сообщение с вашим отзывом."
        )
    elif data.startswith("skip_review_"):
        parts = data.split("_")
        question_id = parts[2]
        stars = int(parts[3])
        
        question = question_bot.questions.get(question_id)
        if question:
            admin_id = question['admin_id']
            user = query.from_user
            
            review_system.add_review(admin_id, stars, "", user.id, user.username or user.first_name)
            
            stats = review_system.get_admin_stats(admin_id)
            admin_info = ADMINS[admin_id]
            
            await query.edit_message_text(
                f"✅ Спасибо! Ваша оценка сохранена!\n\n"
                f"📊 Рейтинг администратора {admin_info['name']} обновлён:\n"
                f"{review_system.get_rating_stars(int(round(stats['average_rating'])))} {stats['average_rating']:.1f}/5\n"
                f"(на основе {stats['total_ratings']} оценок)"
            )

async def show_ratings_info(query):
    """Показывает рейтинги администраторов"""
    ratings_text = "⭐ РЕЙТИНГИ АДМИНИСТРАТОРОВ\n\n"
    
    has_ratings = False
    for admin_id, admin_info in ADMINS.items():
        stats = review_system.get_admin_stats(admin_id)
        
        if stats['total_ratings'] > 0:
            has_ratings = True
            stars = review_system.get_rating_stars(int(round(stats['average_rating'])))
            ratings_text += f"👤 {admin_info['name']} (@{admin_info['username']})\n"
            ratings_text += f"{stars} {stats['average_rating']:.1f}/5\n"
            ratings_text += f"📊 На основе {stats['total_ratings']} оценок\n"
            
            if stats['total_reviews'] > 0:
                ratings_text += f"📝 Отзывов: {stats['total_reviews']}\n"
            
            ratings_text += "────────────────────\n\n"
    
    if not has_ratings:
        ratings_text += "📊 Пока нет оценок\nПервый, кто получит ответ от администратора, сможет поставить оценку!"
    
    keyboard = [
        [InlineKeyboardButton("📝 Задать вопрос", callback_data="choose_admin")],
        [InlineKeyboardButton("👥 Администраторы", callback_data="show_admins")],
        [InlineKeyboardButton("🔙 Главное меню", callback_data="back_to_start")]
    ]
    
    await query.edit_message_text(
        ratings_text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def show_admins_info(query):
    """Показывает информацию обо всех администраторах"""
    keyboard = []
    
    for admin_id, admin_info in ADMINS.items():
        stats = review_system.get_admin_stats(admin_id)
        rating_text = f" ({stats['average_rating']:.1f}⭐)" if stats['total_ratings'] > 0 else ""
        button_text = f"👤 {admin_info['name']}{rating_text}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"admininfo_{admin_id}")])
    
    keyboard.append([InlineKeyboardButton("📝 Задать вопрос", callback_data="choose_admin")])
    keyboard.append([InlineKeyboardButton("⭐ Рейтинги", callback_data="show_ratings")])
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
    stats = review_system.get_admin_stats(admin_id)
    
    info_text = (
        f"👤 {admin_info['name']}\n"
        f"📧 @{admin_info['username']}\n\n"
    )
    
    if stats['total_ratings'] > 0:
        stars = review_system.get_rating_stars(int(round(stats['average_rating'])))
        info_text += f"⭐ Рейтинг: {stars} {stats['average_rating']:.1f}/5\n"
        info_text += f"📊 На основе {stats['total_ratings']} оценок\n\n"
    
    info_text += (
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
    
    for admin_id, admin_info in ADMINS.items():
        stats = review_system.get_admin_stats(admin_id)
        rating_text = f" ({stats['average_rating']:.1f}⭐)" if stats['total_ratings'] > 0 else ""
        button_text = f"👤 {admin_info['name']} (@{admin_info['username']}){rating_text}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"admin_{admin_id}")])
    
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
        "4. Ожидайте ответа\n"
        "5. Оцените помощь администратора (1-5⭐)\n\n"
        "👨‍💼 Наши администраторы:\n"
    )
    
    for admin_id, admin_info in ADMINS.items():
        stats = review_system.get_admin_stats(admin_id)
        rating_text = f" ({stats['average_rating']:.1f}⭐)" if stats['total_ratings'] > 0 else ""
        help_text += f"• {admin_info['name']} (@{admin_info['username']}){rating_text}\n"
    
    keyboard = [
        [InlineKeyboardButton("📝 Задать вопрос", callback_data="choose_admin")],
        [InlineKeyboardButton("👥 Администраторы", callback_data="show_admins")],
        [InlineKeyboardButton("⭐ Рейтинги", callback_data="show_ratings")],
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
    
    # Проверка лимита запросов
    if rate_limiter.is_limited(user.id):
        await update.message.reply_text("❌ Слишком много запросов. Подождите минуту.")
        return
    
    logging.info(f"Message from {user.id}: {message_text[:50]}...")
    
    # Пользователь задает вопрос
    if context.user_data.get('awaiting_question') and context.user_data.get('selected_admin'):
        context.user_data['awaiting_question'] = False
        admin_id = context.user_data['selected_admin']
        
        # Валидация вопроса
        is_valid, error_msg = validate_question_text(message_text)
        if not is_valid:
            await update.message.reply_text(error_msg)
            return
        
        # Проверка на частые вопросы
        recent_questions = question_bot.get_user_recent_questions(user.id)
        if len(recent_questions) >= 3:
            await update.message.reply_text(
                "❌ Вы задали слишком много вопросов за последние 24 часа.\n"
                "Пожалуйста, подождите перед отправкой нового вопроса."
            )
            return
        
        question_id = generate_unique_question_id()
        
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
        
        await notify_admin(update, context, question_id, user, message_text, admin_id)
        context.user_data.pop('selected_admin', None)
        
    # Администратор отвечает на вопрос
    elif context.user_data.get('answering_question'):
        question_id = context.user_data['answering_question']
        admin_response = message_text
        
        if question_id in question_bot.questions:
            question_data = question_bot.questions[question_id]
            
            question_bot.update_question_status(
                question_id=question_id,
                status='answered',
                answer=admin_response
            )
            
            try:
                await context.bot.send_message(
                    chat_id=question_data['user_id'],
                    text=f"💌 Ответ на ваш вопрос #{question_id}:\n\n"
                         f"{admin_response}\n\n"
                         f"С уважением, администратор"
                )
                
                await ask_for_rating(context, question_id, question_data['user_id'])
                await update.message.reply_text("✅ Ответ отправлен пользователю!")
                
                log_admin_action(update.effective_user.id, "answered_question", question_id)
            except Exception as e:
                logging.error(f"Error sending answer: {e}")
                await update.message.reply_text(f"❌ Не удалось отправить ответ: {e}")
            
            context.user_data.pop('answering_question', None)
        else:
            await update.message.reply_text("❌ Вопрос не найден!")
            context.user_data.pop('answering_question', None)
    
    # Пользователь оставляет текстовый отзыв
    elif context.user_data.get('awaiting_review'):
        question_id = context.user_data['review_question']
        stars = context.user_data['review_stars']
        review_text = message_text
        
        question = question_bot.questions.get(question_id)
        if question:
            admin_id = question['admin_id']
            
            review_system.add_review(admin_id, stars, review_text, user.id, user.username or user.first_name)
            
            stats = review_system.get_admin_stats(admin_id)
            admin_info = ADMINS[admin_id]
            
            await update.message.reply_text(
                f"✅ Спасибо! Ваш отзыв сохранён!\n\n"
                f"📊 Рейтинг администратора {admin_info['name']} обновлён:\n"
                f"{review_system.get_rating_stars(int(round(stats['average_rating'])))} {stats['average_rating']:.1f}/5\n"
                f"(на основе {stats['total_ratings']} оценок)"
            )
            
            await notify_admin_about_review(context, admin_id, stars, review_text, user)
        
        context.user_data.pop('awaiting_review', None)
        context.user_data.pop('review_question', None)
        context.user_data.pop('review_stars', None)
    
    else:
        keyboard = [
            [InlineKeyboardButton("📝 Выбрать администратора", callback_data="choose_admin")],
            [InlineKeyboardButton("👥 Информация об администраторах", callback_data="show_admins")],
            [InlineKeyboardButton("⭐ Рейтинги", callback_data="show_ratings")]
        ]
        await update.message.reply_text(
            "Чтобы задать вопрос, выберите администратора из списка:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def ask_for_rating(context, question_id, user_id):
    """Предлагает пользователю оценить ответ"""
    keyboard = [
        [
            InlineKeyboardButton("1⭐", callback_data=f"rate_{question_id}_1"),
            InlineKeyboardButton("2⭐", callback_data=f"rate_{question_id}_2"),
            InlineKeyboardButton("3⭐", callback_data=f"rate_{question_id}_3"),
            InlineKeyboardButton("4⭐", callback_data=f"rate_{question_id}_4"),
            InlineKeyboardButton("5⭐", callback_data=f"rate_{question_id}_5")
        ]
    ]
    
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text="💫 Оцените качество помощи администратора:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        logging.error(f"Error sending rating request: {e}")

async def notify_admin_about_review(context, admin_id, stars, review_text, user):
    """Уведомляет администратора о новом отзыве"""
    stars_display = review_system.get_rating_stars(stars)
    
    message_text = (
        f"⭐ НОВЫЙ ОТЗЫВ!\n\n"
        f"👤 От: {user.first_name}\n"
        f"📱 @{user.username or 'без username'}\n"
        f"🆔 ID: {user.id}\n\n"
        f"Оценка: {stars_display}\n\n"
        f"📝 Отзыв:\n{review_text}\n\n"
        f"⏰ {datetime.now().strftime('%H:%M %d.%m.%Y')}"
    )
    
    try:
        await context.bot.send_message(
            chat_id=admin_id,
            text=message_text
        )
        logging.info(f"Review notification sent to admin {admin_id}")
    except Exception as e:
        logging.error(f"Error sending review notification to admin {admin_id}: {e}")

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
        logging.info(f"Notification sent to admin {admin_id}")
    except Exception as e:
        logging.error(f"Error sending notification to admin {admin_id}: {e}")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ошибок"""
    error = context.error
    logging.error(f"Error: {error}")

def main():
    """Основная функция запуска бота"""
    print("=" * 50)
    print("🤖 БОТ ДЛЯ СВЯЗИ С АДМИНИСТРАТОРАМИ")
    print("=" * 50)
    print("✅ Токен бота: Установлен")
    print("✅ Администраторы:")
    for admin_id, admin_info in ADMINS.items():
        print(f"   👤 {admin_info['name']} (@{admin_info['username']}) - ID: {admin_id}")
    print(f"✅ Загружено вопросов: {len(question_bot.questions)}")
    print(f"✅ Загружено отзывов: {sum(len(admin_data['reviews']) for admin_data in review_system.reviews.values())}")
    print("=" * 50)
    
    # Запускаем health check сервер
    health_thread = threading.Thread(target=run_health_check, daemon=True)
    health_thread.start()
    logging.info("Health check server started")
    
    try:
        application = Application.builder().token(BOT_TOKEN).build()
        
        handlers = [
            CommandHandler("start", start_command),
            CommandHandler("help", help_command),
            CommandHandler("admin", admin_command),
            CommandHandler("stats", stats_command),
            CommandHandler("graph", graph_command),
            CommandHandler("ratings", ratings_command),
            CommandHandler("ping", ping_command),
            CommandHandler("reload", reload_command),
            CommandHandler("cleanup", cleanup_command),
            CallbackQueryHandler(button_handler),
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
        ]
        
        for handler in handlers:
            application.add_handler(handler)
        
        application.add_error_handler(error_handler)
        
        logging.info("Starting bot...")
        application.run_polling(
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES
        )
        
    except Exception as e:
        logging.error(f"Critical error: {e}")

if __name__ == '__main__':
    main()
