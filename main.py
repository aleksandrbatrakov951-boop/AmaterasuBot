import logging
import os
import json
import threading
import time
import asyncio
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime, timedelta
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
USER_PREFERENCES_FILE = "user_preferences.json"  # Новый файл для пользовательских предпочтений

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

# ==================== СИСТЕМА НАПОМИНАНИЙ ====================
class ReminderSystem:
    def __init__(self):
        self.reminders_sent = set()  # Чтобы не дублировать напоминания
    
    async def check_pending_questions(self, context: ContextTypes.DEFAULT_TYPE):
        """Проверяет неотвеченные вопросы и отправляет напоминания"""
        try:
            current_time = datetime.now()
            reminder_count = 0
            
            for question_id, question_data in question_bot.questions.items():
                if question_data['status'] == 'new':
                    question_time = datetime.fromisoformat(question_data['timestamp'])
                    time_diff = current_time - question_time
                    
                    reminder_key = f"{question_id}_{int(time_diff.total_seconds() // 3600)}"
                    
                    # Напоминание через 1 час (если еще не отправляли)
                    if timedelta(hours=1) <= time_diff < timedelta(hours=1, minutes=10) and reminder_key not in self.reminders_sent:
                        await self.send_reminder(context, question_id, question_data, "1 час")
                        self.reminders_sent.add(reminder_key)
                        reminder_count += 1
                    
                    # Напоминание через 3 часа
                    elif timedelta(hours=3) <= time_diff < timedelta(hours=3, minutes=10) and reminder_key not in self.reminders_sent:
                        await self.send_reminder(context, question_id, question_data, "3 часа")
                        self.reminders_sent.add(reminder_key)
                        reminder_count += 1
                    
                    # Напоминание через 6 часов
                    elif timedelta(hours=6) <= time_diff < timedelta(hours=6, minutes=10) and reminder_key not in self.reminders_sent:
                        await self.send_reminder(context, question_id, question_data, "6 часов")
                        self.reminders_sent.add(reminder_key)
                        reminder_count += 1
            
            if reminder_count > 0:
                print(f"✅ Отправлено {reminder_count} напоминаний")
                
        except Exception as e:
            print(f"❌ Ошибка в системе напоминаний: {e}")
    
    async def send_reminder(self, context, question_id, question_data, time_passed):
        """Отправляет напоминание администратору"""
        admin_id = question_data['admin_id']
        
        reminder_text = (
            f"⏰ НАПОМИНАНИЕ\n\n"
            f"Вопрос #{question_id} ждет ответа уже {time_passed}:\n\n"
            f"❓ {question_data['question'][:100]}...\n\n"
            f"👤 От: {question_data['username']}\n"
            f"🕒 Задан: {datetime.fromisoformat(question_data['timestamp']).strftime('%H:%M %d.%m.%Y')}\n\n"
            f"Не забудьте ответить пользователю!"
        )
        
        keyboard = [[InlineKeyboardButton("📝 Ответить сейчас", callback_data=f"answer_{question_id}")]]
        
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=reminder_text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            print(f"✅ Напоминание отправлено админу {admin_id} по вопросу #{question_id}")
        except Exception as e:
            print(f"❌ Ошибка отправки напоминания: {e}")

# ==================== СИСТЕМА ПРЕДПОЧТЕНИЙ ПОЛЬЗОВАТЕЛЕЙ ====================
class UserPreferences:
    def __init__(self):
        self.preferences = {}
        self.load_preferences()
    
    def load_preferences(self):
        """Загружает предпочтения пользователей из файла"""
        try:
            if os.path.exists(USER_PREFERENCES_FILE):
                with open(USER_PREFERENCES_FILE, 'r', encoding='utf-8') as f:
                    self.preferences = json.load(f)
                    print(f"✅ Загружено предпочтений для {len(self.preferences)} пользователей")
            else:
                self.preferences = {}
                print("✅ Файл предпочтений создан заново")
        except Exception as e:
            print(f"❌ Ошибка загрузки предпочтений: {e}")
            self.preferences = {}
    
    def save_preferences(self):
        """Сохраняет предпочтения в файл"""
        try:
            with open(USER_PREFERENCES_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.preferences, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"❌ Ошибка сохранения предпочтений: {e}")
    
    def update_favorite_admin(self, user_id, admin_id):
        """Обновляет любимого админа пользователя"""
        if str(user_id) not in self.preferences:
            self.preferences[str(user_id)] = {}
        
        self.preferences[str(user_id)]['favorite_admin'] = admin_id
        self.preferences[str(user_id)]['last_used'] = datetime.now().isoformat()
        self.save_preferences()
        print(f"✅ Обновлен любимый админ для пользователя {user_id}: {admin_id}")
    
    def get_favorite_admin(self, user_id):
        """Возвращает любимого админа пользователя"""
        user_prefs = self.preferences.get(str(user_id), {})
        return user_prefs.get('favorite_admin')

# ==================== СУЩЕСТВУЮЩИЕ СИСТЕМЫ ====================
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

# Создаем экземпляры всех систем
question_bot = QuestionBot()
review_system = ReviewSystem()
reminder_system = ReminderSystem()
user_preferences = UserPreferences()

# ==================== ОБНОВЛЕННЫЕ КОМАНДЫ ====================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start с умным стартом"""
    user = update.effective_user
    user_id = user.id
    
    # Проверяем, есть ли у пользователя "любимый" админ
    favorite_admin = user_preferences.get_favorite_admin(user_id)
    
    keyboard = []
    
    if favorite_admin and favorite_admin in ADMINS:
        admin_info = ADMINS[favorite_admin]
        # Предлагаем быстрый доступ к часто используемому админу
        keyboard.append([InlineKeyboardButton(f"🚀 К {admin_info['name']} (быстрый доступ)", callback_data=f"admin_{favorite_admin}")])
    
    keyboard.extend([
        [InlineKeyboardButton("📝 Задать вопрос", callback_data="choose_admin")],
        [InlineKeyboardButton("👥 Администраторы", callback_data="show_admins")],
        [InlineKeyboardButton("⭐ Рейтинги", callback_data="show_ratings")],
        [InlineKeyboardButton("ℹ️ Помощь", callback_data="help")]
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = f"Привет, {user.first_name}! 👋\n\n"
    
    if favorite_admin:
        welcome_text += f"Часто обращаетесь к {ADMINS[favorite_admin]['name']}? Можете сразу написать ему!"
    else:
        welcome_text += "Я бот для связи с администраторами. Вы можете задать вопрос конкретному администратору."
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)

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
        "🚀 Новые функции:\n"
        "• Умный старт - бот запоминает вашего админа\n"
        "• Быстрые реакции - мгновенная обратная связь\n"
        "• Авто-напоминания - админы не забудут ответить\n\n"
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
    
    # Считаем активные напоминания
    active_reminders = len([q for q in question_bot.questions.values() if q['status'] == 'new'])
    
    ping_text = (
        f"🏓 PONG!\n\n"
        f"🤖 Бот работает исправно\n"
        f"👤 Пользователь: {user.first_name}\n"
        f"🆔 ID: {user.id}\n"
        f"⏰ Время сервера: {current_time}\n"
        f"⏱ Аптайм: {uptime}\n"
        f"📊 Вопросов в базе: {len(question_bot.questions)}\n"
        f"📨 Активных вопросов: {active_reminders}\n"
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
    
    # Перезагружаем все системы
    question_bot.load_questions()
    new_count = len(question_bot.questions)
    review_system.load_reviews()
    user_preferences.load_preferences()
    
    # Очищаем user_data для предотвращения конфликтов
    if update.effective_user.id in context.user_data:
        context.user_data.clear()
    
    await update.message.reply_text(
        f"🔄 Данные бота перезагружены!\n\n"
        f"📊 Вопросов в базе:\n"
        f"• Было: {old_count}\n"
        f"• Стало: {new_count}\n\n"
        f"✅ Все системы перезагружены\n"
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

# ==================== ОБНОВЛЕННЫЙ ОБРАБОТЧИК КНОПОК ====================
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
        # Пользователь выбрал администратора
        admin_id = int(data.split("_")[1])
        context.user_data['selected_admin'] = admin_id
        context.user_data['awaiting_question'] = True
        
        # Сохраняем выбор как предпочтение пользователя
        user_preferences.update_favorite_admin(query.from_user.id, admin_id)
        
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
    
    # Обработка оценок
    elif data.startswith("rate_"):
        parts = data.split("_")
        question_id = parts[1]
        stars = int(parts[2])
        
        context.user_data['rated_question'] = question_id
        context.user_data['rating_stars'] = stars
        
        # Предлагаем оставить отзыв
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
            
            # Сохраняем оценку без отзыва
            review_system.add_review(admin_id, stars, "", user.id, user.username or user.first_name)
            
            stats = review_system.get_admin_stats(admin_id)
            admin_info = ADMINS[admin_id]
            
            await query.edit_message_text(
                f"✅ Спасибо! Ваша оценка сохранена!\n\n"
                f"📊 Рейтинг администратора {admin_info['name']} обновлён:\n"
                f"{review_system.get_rating_stars(int(round(stats['average_rating'])))} {stats['average_rating']:.1f}/5\n"
                f"(на основе {stats['total_ratings']} оценок)"
            )
    
    # ==================== БЫСТРЫЕ РЕАКЦИИ ====================
    elif data.startswith("react_"):
        parts = data.split("_")
        question_id = parts[1]
        reaction_type = parts[2]
        
        question = question_bot.questions.get(question_id)
        if question:
            admin_id = question['admin_id']
            user = query.from_user
            
            reaction_emojis = {
                'thanks': '🙏',
                'good': '👍', 
                'excellent': '⭐',
                'clarify': '❓'
            }
            
            reaction_texts = {
                'thanks': 'Спасибо за помощь!',
                'good': 'Понятно, спасибо!',
                'excellent': 'Отличный ответ!', 
                'clarify': 'Нужно уточнение'
            }
            
            # Отправляем реакцию админу
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=f"{reaction_emojis[reaction_type]} Пользователь отреагировал на ваш ответ:\n"
                         f"\"{reaction_texts[reaction_type]}\"\n\n"
                         f"💬 Вопрос #{question_id}\n"
                         f"👤 От: {user.first_name} (@{user.username or 'без username'})"
                )
                
                await query.edit_message_text(
                    f"{reaction_emojis[reaction_type]} Ваша реакция отправлена!\n"
                    f"Администратор увидел: \"{reaction_texts[reaction_type]}\""
                )
                
                print(f"✅ Реакция отправлена админу {admin_id}: {reaction_type}")
                
            except Exception as e:
                await query.edit_message_text("❌ Не удалось отправить реакцию")
                print(f"❌ Ошибка отправки реакции: {e}")

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================
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
    
    # Создаем кнопки для просмотра информации о каждом администраторе
    for admin_id, admin_info in ADMINS.items():
        # Добавляем рейтинг к имени администратора
        stats = review_system.get_admin_stats(admin_id)
        rating_text = f" ({stats['average_rating']:.1f}⭐)" if stats['total_ratings'] > 0 else ""
        button_text = f"👤 {admin_info['name']}{rating_text}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"admininfo_{admin_id}")])
    
    # Добавляем кнопки действий
    keyboard.append([InlineKeyboardButton("📝 Задать вопрос", callback_data="choose_admin")])
    keyboard.append([InlineKeyboardButton("⭐ Рейтинги", callback_data="show_ratings")])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back_to_start")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    admin_list = "\n".join([f"• {info['name']} (@{info['username']})" for info in ADMINS.values()])
    
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
    
    # Создаем информационное сообщение
    info_text = (
        f"👤 {admin_info['name']}\n"
        f"📧 @{admin_info['username']}\n\n"
    )
    
    # Добавляем рейтинг, если есть
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
    
    # Получаем любимого админа пользователя
    favorite_admin = user_preferences.get_favorite_admin(query.from_user.id)
    
    # Создаем кнопки для каждого администратора
    for admin_id, admin_info in ADMINS.items():
        # Добавляем рейтинг к имени
        stats = review_system.get_admin_stats(admin_id)
        rating_text = f" ({stats['average_rating']:.1f}⭐)" if stats['total_ratings'] > 0 else ""
        
        # Помечаем любимого админа
        favorite_emoji = "⭐ " if admin_id == favorite_admin else ""
        
        button_text = f"{favorite_emoji}👤 {admin_info['name']} (@{admin_info['username']}){rating_text}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"admin_{admin_id}")])
    
    # Добавляем кнопку назад
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back_to_start")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    admin_list = "\n".join([f"• {info['name']} (@{info['username']})" for info in ADMINS.values()])
    
    await query.edit_message_text(
        f"👥 Выберите администратора:\n\n"
        f"{admin_list}\n\n"
        f"💡 Бот запомнит вашего частого админа для быстрого доступа!",
        reply_markup=reply_markup
    )

async def help_callback(query):
    """Показывает помощь в inline режиме"""
    help_text = (
        "🤖 Как пользоваться боту:\n\n"
        "1. Нажмите 'Задать вопрос'\n"
        "2. Выберите администратора из списка\n"
        "3. Напишите ваш вопрос\n"
        "4. Ожидайте ответа\n"
        "5. Оцените помощь администратора (1-5⭐)\n\n"
        "🚀 Новые функции:\n"
        "• Умный старт - бот запоминает вашего админа\n"
        "• Быстрые реакции - мгновенная обратная связь\n"
        "• Авто-напоминания - админы не забудут ответить\n\n"
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

# ==================== ОБНОВЛЕННЫЙ ОБРАБОТЧИК СООБЩЕНИЙ ====================
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
            f"Администратор уведомлен и ответит вам в ближайшее время.\n"
            f"⏰ Вы получите уведомление когда придет ответ!"
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
                
                # Предлагаем оценить ответ с быстрыми реакциями
                await ask_for_rating(context, question_id, question_data['user_id'])
                
                await update.message.reply_text("✅ Ответ отправлен пользователю!")
            except Exception as e:
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
            
            # Сохраняем отзыв
            review_system.add_review(admin_id, stars, review_text, user.id, user.username or user.first_name)
            
            stats = review_system.get_admin_stats(admin_id)
            admin_info = ADMINS[admin_id]
            
            await update.message.reply_text(
                f"✅ Спасибо! Ваш отзыв сохранён!\n\n"
                f"📊 Рейтинг администратора {admin_info['name']} обновлён:\n"
                f"{review_system.get_rating_stars(int(round(stats['average_rating'])))} {stats['average_rating']:.1f}/5\n"
                f"(на основе {stats['total_ratings']} оценок)"
            )
            
            # Уведомляем администратора о новом отзыве
            await notify_admin_about_review(context, admin_id, stars, review_text, user)
        
        context.user_data.pop('awaiting_review', None)
        context.user_data.pop('review_question', None)
        context.user_data.pop('review_stars', None)
    
    else:
        # Если просто текст - предлагаем выбрать администратора
        keyboard = [
            [InlineKeyboardButton("📝 Выбрать администратора", callback_data="choose_admin")],
            [InlineKeyboardButton("👥 Информация об администраторах", callback_data="show_admins")],
            [InlineKeyboardButton("⭐ Рейтинги", callback_data="show_ratings")]
        ]
        await update.message.reply_text(
            "Чтобы задать вопрос, выберите администратора из списка:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

# ==================== ОБНОВЛЕННАЯ ФУНКЦИЯ ОЦЕНКИ ====================
async def ask_for_rating(context, question_id, user_id):
    """Предлагает пользователю оценить ответ с быстрыми реакциями"""
    reaction_keyboard = [
        [
            InlineKeyboardButton("🙏 Спасибо", callback_data=f"react_{question_id}_thanks"),
            InlineKeyboardButton("👍 Понятно", callback_data=f"react_{question_id}_good"),
        ],
        [
            InlineKeyboardButton("⭐ Отлично", callback_data=f"react_{question_id}_excellent"),
            InlineKeyboardButton("❓ Уточнить", callback_data=f"react_{question_id}_clarify"),
        ],
        [
            InlineKeyboardButton("💫 Подробная оценка", callback_data=f"rate_{question_id}_detailed")
        ]
    ]
    
    try:
        # Сначала предлагаем быстрые реакции
        await context.bot.send_message(
            chat_id=user_id,
            text="💬 Как вам ответ?\n\nВыберите быструю реакцию или подробную оценку:",
            reply_markup=InlineKeyboardMarkup(reaction_keyboard)
        )
        
    except Exception as e:
        print(f"❌ Не удалось отправить запрос на оценку: {e}")

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
        print(f"✅ Уведомление об отзыве отправлено админу {admin_id}")
    except Exception as e:
        print(f"❌ Ошибка отправки уведомления об отзыве админу {admin_id}: {e}")

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

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ошибок"""
    error = context.error
    logging.error(f"Ошибка: {error}")

# ==================== ФОН
