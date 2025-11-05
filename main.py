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
REVIEWS_FILE = "reviews.json"
ACTIVATIONS_FILE = "activations.json"

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

class ActivationTracker:
    def __init__(self):
        self.activations = {}
        self.load_activations()
    
    def load_activations(self):
        """Загружает данные об активациях из файла"""
        try:
            if os.path.exists(ACTIVATIONS_FILE):
                with open(ACTIVATIONS_FILE, 'r', encoding='utf-8') as f:
                    self.activations = json.load(f)
                    print(f"✅ Загружено {len(self.activations)} записей об активациях")
            else:
                self.activations = {}
                print("✅ Файл активаций создан заново")
        except Exception as e:
            print(f"❌ Ошибка загрузки активаций: {e}")
            self.activations = {}
    
    def save_activations(self):
        """Сохраняет данные об активациях в файл"""
        try:
            with open(ACTIVATIONS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.activations, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"❌ Ошибка сохранения активаций: {e}")
    
    def is_new_user(self, user_id):
        """Проверяет, является ли пользователь новым"""
        return str(user_id) not in self.activations
    
    def add_activation(self, user_id, username, first_name, last_name=None):
        """Добавляет запись об активации"""
        user_id_str = str(user_id)
        self.activations[user_id_str] = {
            'username': username,
            'first_name': first_name,
            'last_name': last_name,
            'first_activation': datetime.now().isoformat(),
            'last_activation': datetime.now().isoformat(),
            'activation_count': 1
        }
        self.save_activations()
        return True
    
    def update_activation(self, user_id):
        """Обновляет запись об активации для существующего пользователя"""
        user_id_str = str(user_id)
        if user_id_str in self.activations:
            self.activations[user_id_str]['last_activation'] = datetime.now().isoformat()
            self.activations[user_id_str]['activation_count'] += 1
            self.save_activations()
            return False  # Не новый пользователь
        return True  # Новый пользователь

def create_bar(percentage, max_percentage=100):
    """Создает текстовый график-прогрессбар"""
    bars = 10
    filled = int((percentage / max_percentage) * bars)
    empty = bars - filled
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

# Создаем экземпляры
question_bot = QuestionBot()
review_system = ReviewSystem()
activation_tracker = ActivationTracker()

async def notify_admins_about_activation(context: ContextTypes.DEFAULT_TYPE, user, is_new_user):
    """Уведомляет всех администраторов о новой активации"""
    current_time = datetime.now().strftime('%H:%M:%S %d.%m.%Y')
    
    if is_new_user:
        message_text = (
            f"🎉 НОВЫЙ ПОЛЬЗОВАТЕЛЬ АКТИВИРОВАЛ БОТА!\n\n"
            f"👤 Имя: {user.first_name}\n"
            f"📱 Username: @{user.username or 'не указан'}\n"
            f"🆔 ID: {user.id}\n"
            f"⏰ Время: {current_time}\n\n"
            f"📊 Всего пользователей: {len(activation_tracker.activations)}"
        )
    else:
        message_text = (
            f"🔄 ПОЛЬЗОВАТЕЛЬ ПЕРЕЗАПУСТИЛ БОТА\n\n"
            f"👤 Имя: {user.first_name}\n"
            f"📱 Username: @{user.username or 'не указан'}\n"
            f"🆔 ID: {user.id}\n"
            f"⏰ Время: {current_time}\n\n"
            f"📊 Всего пользователей: {len(activation_tracker.activations)}"
        )
    
    for admin_id in ADMINS.keys():
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=message_text
            )
            print(f"✅ Уведомление об активации отправлено админу {admin_id}")
        except Exception as e:
            print(f"❌ Ошибка отправки уведомления админу {admin_id}: {e}")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    
    # Отслеживаем активацию
    is_new_user = activation_tracker.is_new_user(user.id)
    if is_new_user:
        activation_tracker.add_activation(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name
        )
    else:
        activation_tracker.update_activation(user.id)
    
    # Уведомляем администраторов
    await notify_admins_about_activation(context, user, is_new_user)
    
    keyboard = [
        [InlineKeyboardButton("📝 Задать вопрос", callback_data="choose_admin")],
        [InlineKeyboardButton("👥 Администраторы", callback_data="show_admins")],
        [InlineKeyboardButton("⭐ Рейтинги", callback_data="show_ratings")],
        [InlineKeyboardButton("ℹ️ Помощь", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = f"Привет, {user.first_name}! 👋\n\n"
    if is_new_user:
        welcome_text += "🎉 Добро пожаловать! Я бот для связи с администраторами.\n"
    else:
        welcome_text += "С возвращением! Я бот для связи с администраторами.\n"
    
    welcome_text += "Вы можете задать вопрос конкретному администратору."
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=reply_markup
    )

async def activations_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для просмотра статистики активаций (только для админов)"""
    user_id = update.effective_user.id
    
    if user_id not in ADMINS:
        await update.message.reply_text("❌ У вас нет прав администратора.")
        return
    
    total_users = len(activation_tracker.activations)
    
    # Считаем активации за последние 24 часа
    yesterday = datetime.now().timestamp() - 24 * 3600
    recent_activations = 0
    
    for user_data in activation_tracker.activations.values():
        last_activation = datetime.fromisoformat(user_data['last_activation']).timestamp()
        if last_activation > yesterday:
            recent_activations += 1
    
    stats_text = (
        f"📊 СТАТИСТИКА АКТИВАЦИЙ\n\n"
        f"👥 Всего пользователей: {total_users}\n"
        f"🔄 Активаций за 24ч: {recent_activations}\n\n"
        f"📈 Последние 5 активаций:\n"
    )
    
    # Сортируем по времени последней активации
    sorted_activations = sorted(
        activation_tracker.activations.items(),
        key=lambda x: x[1]['last_activation'],
        reverse=True
    )[:5]
    
    for user_id_str, user_data in sorted_activations:
        username = user_data['username'] or 'без username'
        last_time = datetime.fromisoformat(user_data['last_activation']).strftime('%H:%M %d.%m')
        stats_text += f"• {user_data['first_name']} (@{username}) - {last_time}\n"
    
    await update.message.reply_text(stats_text)

# Базовые команды (упрощенные версии)
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    help_text = (
        "🤖 Помощь по боту\n\n"
        "📝 Задать вопрос:\n"
        "• Выберите администратора из списка\n"
        "• Напишите ваш вопрос\n\n"
        "⭐ Система отзывов:\n"
        "• После ответа оцените помощь\n\n"
        "👥 Администраторы:\n"
    )
    
    for admin_id, admin_info in ADMINS.items():
        help_text += f"• {admin_info['name']} (@{admin_info['username']})\n"
    
    await update.message.reply_text(help_text)

async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверка работы бота"""
    uptime_seconds = time.time() - START_TIME
    hours = int(uptime_seconds // 3600)
    minutes = int((uptime_seconds % 3600) // 60)
    uptime = f"{hours}ч {minutes}м"
    
    await update.message.reply_text(
        f"🏓 PONG!\n"
        f"⏱ Аптайм: {uptime}\n"
        f"✅ Бот работает"
    )

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для администраторов"""
    user_id = update.effective_user.id
    if user_id not in ADMINS:
        await update.message.reply_text("❌ У вас нет прав администратора.")
        return
    await update.message.reply_text("👨‍💼 Панель администратора")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Общая статистика"""
    total = len(question_bot.questions)
    new = len([q for q in question_bot.questions.values() if q['status'] == 'new'])
    answered = len([q for q in question_bot.questions.values() if q['status'] == 'answered'])
    
    stats_text = (
        f"📊 Статистика:\n"
        f"• Всего вопросов: {total}\n"
        f"• Новых: {new}\n"
        f"• Отвечено: {answered}"
    )
    await update.message.reply_text(stats_text)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на кнопки"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "help":
        await help_callback(query)
    elif query.data == "back_to_start":
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
    else:
        await query.edit_message_text("Функция в разработке")

async def help_callback(query):
    """Показывает помощь в inline режиме"""
    await query.edit_message_text(
        "🤖 Помощь по боту\n\nИспользуйте кнопки для навигации",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="back_to_start")]])
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    await update.message.reply_text(
        "Чтобы задать вопрос, используйте кнопку 'Задать вопрос' в меню"
    )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ошибок"""
    error = context.error
    logging.error(f"Ошибка: {error}")

def main():
    """Основная функция запуска бота"""
    print("=" * 60)
    print("🤖 БОТ ДЛЯ СВЯЗИ С АДМИНИСТРАТОРАМИ")
    print("=" * 60)
    print(f"✅ Зарегистрировано пользователей: {len(activation_tracker.activations)}")
    print("=" * 60)
    
    # Запускаем health check сервер
    health_thread = threading.Thread(target=run_health_check, daemon=True)
    health_thread.start()
    print("✅ Health check server запущен")
    
    try:
        application = Application.builder().token(BOT_TOKEN).build()
        
        handlers = [
            CommandHandler("start", start_command),
            CommandHandler("help", help_command),
            CommandHandler("admin", admin_command),
            CommandHandler("stats", stats_command),
            CommandHandler("activations", activations_command),
            CommandHandler("ping", ping_command),
            CallbackQueryHandler(button_handler),
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
        ]
        
        for handler in handlers:
            application.add_handler(handler)
        
        application.add_error_handler(error_handler)
        
        print("🔄 Запускаем бота...")
        application.run_polling(drop_pending_updates=True)
        
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")

if __name__ == '__main__':
    main()
