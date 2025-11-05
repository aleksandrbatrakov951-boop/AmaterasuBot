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
REVIEWS_FILE = "reviews.json"  # Новый файл для отзывов

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

def create_bar(percentage, max_percentage=100):
    """Создает текстовый график-прогрессбар"""
    bars = 10  # количество символов в прогрессбаре
    filled = int((percentage / max_percentage) * bars)
    empty = bars - filled
    
    # Используем разные символы для заполненной и пустой частей
    filled_char = "▰"
    empty_char = "▱"
    
    return filled_char * filled + empty_char * empty

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
                    print(f"✅ Загружено отзывов для {len(self.reviews)} администраторов")
            else:
                self.reviews = {}
                print("✅ Файл отзывов создан заново")
        except Exception as e:
            print(f"❌ Ошибка загрузки отзывов: {e}")
            self.reviews = {}
    
    def save_reviews(self):
        """Сохраняет отзывы в файл"""
        try:
            with open(REVIEWS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.reviews, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"❌ Ошибка сохранения отзывов: {e}")
    
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
        
        # Пересчитываем средний рейтинг
        ratings = self.reviews[str(admin_id)]['ratings']
        self.reviews[str(admin_id)]['average_rating'] = sum(ratings) / len(ratings)
        
        self.save_reviews()
        print(f"✅ Добавлен отзыв для админа {admin_id}: {stars} звезд")
    
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
        
        # Считаем распределение оценок
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

# Создаем экземпляры бота и системы отзывов
question_bot = QuestionBot()
review_system = ReviewSystem()

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
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
    
    # Добавляем список администраторов в помощь
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
    
    # Сохраняем текущее состояние
    old_count = len(question_bot.questions)
    
    # Перезагружаем вопросы из файла
    question_bot.load_questions()
    new_count = len(question_bot.questions)
    
    # Перезагружаем отзывы
    review_system.load_reviews()
    
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

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Общая статистика для всех пользователей"""
    total = len(question_bot.questions)
    new = len([q for q in question_bot.questions.values() if q['status'] == 'new'])
    answered = len([q for q in question_bot.questions.values() if q['status'] == 'answered'])
    
    percentage = (answered / max(total, 1)) * 100
    
    # Создаем графики
    total_bar = create_bar(100, 100)  # Общий прогресс
    answered_bar = create_bar(percentage, 100) if total > 0 else "▰▰▰▰▰▰▰▰▰▰"
    
    # Статистика по администраторам
    admin_stats = []
    for admin_id, admin_info in ADMINS.items():
        admin_questions = [q for q in question_bot.questions.values() if q['admin_id'] == admin_id]
        admin_total = len(admin_questions)
        admin_answered = len([q for q in admin_questions if q['status'] == 'answered'])
        admin_percentage = (admin_answered / max(admin_total, 1)) * 100 if admin_total > 0 else 0
        
        # Добавляем рейтинг
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
    
    # Собираем текст статистики
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
    
    # Добавляем статистику по каждому администратору
    for admin in admin_stats:
        stats_text += f"\n👤 {admin['name']}:\n"
        stats_text += f"{admin['bar']} {admin['percentage']:.1f}%\n"
        stats_text += f"• Всего: {admin['total']} | Ответов: {admin['answered']}\n"
        if admin['total_ratings'] > 0:
            stats_text += f"• ⭐ Рейтинг: {admin['rating']:.1f}/5 ({admin['total_ratings']} оценок)\n"
    
    stats_text += f"\n⏰ Бот работает исправно ✅"
    
    await update.message.reply_text(
        stats_text,
        parse_mode='Markdown'
    )

async def graph_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Графическая статистика с эмодзи"""
    total = len(question_bot.questions)
    new = len([q for q in question_bot.questions.values() if q['status'] == 'new'])
    answered = len([q for q in question_bot.questions.values() if q['status'] == 'answered'])
    in_progress = total - new - answered
    
    # Создаем круговую диаграмму из эмодзи
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
    
    # Добавляем статистику администраторов
    for admin_id, admin_info in ADMINS.items():
        admin_questions = [q for q in question_bot.questions.values() if q['admin_id'] == admin_id]
        admin_total = len(admin_questions)
        admin_answered = len([q for q in admin_questions if q['status'] == 'answered'])
        admin_percentage = (admin_answered / max(admin_total, 1)) * 100 if admin_total > 0 else 0
        
        # Добавляем рейтинг
        rating_stats = review_system.get_admin_stats(admin_id)
        rating_text = f" ⭐ {rating_stats['average_rating']:.1f}" if rating_stats['total_ratings'] > 0 else ""
        
        graph_text += f"👤 {admin_info['name']}: {create_small_bar(admin_percentage)} {admin_percentage:.0f}% ({admin_answered}/{admin_total}){rating_text}\n"
    
    await update.message.reply_text(
        graph_text,
        parse_mode='Markdown'
    )

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
            
            # Показываем распределение оценок
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
    
    # Считаем вопросы для этого администратора
    admin_questions = [q for q in question_bot.questions.values() if q['admin_id'] == user_id]
    total = len(admin_questions)
    new = len([q for q in admin_questions if q['status'] == 'new'])
    answered = len([q for q in admin_questions if q['status'] == 'answered'])
    
    admin_info = ADMINS[user_id]
    
    # Добавляем статистику отзывов
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
            [In
