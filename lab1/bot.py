#!/usr/bin/env python3
"""
Telegram News Bot
Бот для сбора новостей по определенным темам и отправки ежедневных дайджестов
"""

import os
import json
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class NewsBot:
    """Основной класс для работы с новостным ботом"""
    
    def __init__(self):
        self.data_file = 'news_data.json'
        self.users_data = self.load_data()
        self.news_api_key = os.getenv('NEWS_API_KEY')
        self.news_api_url = 'https://newsapi.org/v2/everything'
        
    def load_data(self) -> Dict:
        """Загружает данные пользователей из JSON файла"""
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    logger.info(f"Загружены данные для {len(data)} пользователей")
                    return data
            logger.info("Файл данных не найден, создаем новый")
            return {}
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка парсинга JSON: {e}")
            # Создаем резервную копию поврежденного файла
            if os.path.exists(self.data_file):
                backup_file = f"{self.data_file}.backup"
                os.rename(self.data_file, backup_file)
                logger.info(f"Создана резервная копия: {backup_file}")
            return {}
        except Exception as e:
            logger.error(f"Ошибка при загрузке данных: {e}")
            return {}
    
    def save_data(self) -> None:
        """Сохраняет данные пользователей в JSON файл"""
        try:
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(self.users_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Ошибка при сохранении данных: {e}")
    
    def get_news(self, query: str, language: str = 'ru') -> List[Dict]:
        """Получает новости по запросу из NewsAPI"""
        try:
            if not self.news_api_key:
                logger.warning("API ключ для новостей не настроен")
                return []
            
            params = {
                'q': query,
                'language': language,
                'sortBy': 'publishedAt',
                'pageSize': 10,
                'apiKey': self.news_api_key
            }
            
            response = requests.get(self.news_api_url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            return data.get('articles', [])
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при получении новостей: {e}")
            return []
        except Exception as e:
            logger.error(f"Неожиданная ошибка при получении новостей: {e}")
            return []
    
    def filter_news_by_keywords(self, articles: List[Dict], keywords: List[str]) -> List[Dict]:
        """Фильтрует новости по ключевым словам"""
        if not keywords:
            return articles
        
        filtered_articles = []
        for article in articles:
            title = article.get('title', '').lower()
            description = article.get('description', '').lower()
            content = f"{title} {description}"
            
            if any(keyword.lower() in content for keyword in keywords):
                filtered_articles.append(article)
        
        return filtered_articles
    
    def format_news_message(self, articles: List[Dict], topic: str) -> str:
        """Форматирует новости для отправки в Telegram"""
        if not articles:
            return f"📰 По теме '{topic}' новостей не найдено."
        
        message = f"📰 <b>Новости по теме: {topic}</b>\n\n"
        
        for i, article in enumerate(articles[:5], 1):  # Показываем только первые 5 новостей
            title = article.get('title', 'Без заголовка')
            description = article.get('description', '')
            url = article.get('url', '')
            published_at = article.get('publishedAt', '')
            
            # Форматируем дату
            try:
                if published_at:
                    date_obj = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
                    formatted_date = date_obj.strftime('%d.%m.%Y %H:%M')
                else:
                    formatted_date = 'Дата неизвестна'
            except:
                formatted_date = 'Дата неизвестна'
            
            message += f"{i}. <b>{title}</b>\n"
            if description:
                message += f"   {description[:200]}{'...' if len(description) > 200 else ''}\n"
            if url:
                message += f"   🔗 <a href='{url}'>Читать далее</a>\n"
            message += f"   📅 {formatted_date}\n\n"
        
        return message
    
    def add_user_topic(self, user_id: int, topic: str, keywords: List[str] = None) -> None:
        """Добавляет тему для пользователя"""
        if user_id not in self.users_data:
            self.users_data[user_id] = {
                'topics': [],
                'keywords': [],
                'daily_digest': True,
                'last_digest': None
            }
        
        if keywords is None:
            keywords = []
        
        self.users_data[user_id]['topics'].append({
            'name': topic,
            'keywords': keywords,
            'added_at': datetime.now().isoformat()
        })
        
        self.save_data()
    
    def remove_user_topic(self, user_id: int, topic: str) -> bool:
        """Удаляет тему у пользователя"""
        if user_id not in self.users_data:
            return False
        
        topics = self.users_data[user_id]['topics']
        self.users_data[user_id]['topics'] = [t for t in topics if t['name'] != topic]
        
        self.save_data()
        return True
    
    def get_user_topics(self, user_id: int) -> List[Dict]:
        """Получает темы пользователя"""
        if user_id not in self.users_data:
            return []
        return self.users_data[user_id].get('topics', [])
    
    def toggle_daily_digest(self, user_id: int) -> bool:
        """Переключает ежедневные дайджесты для пользователя"""
        if user_id not in self.users_data:
            self.users_data[user_id] = {
                'topics': [],
                'keywords': [],
                'daily_digest': True,
                'last_digest': None
            }
        
        self.users_data[user_id]['daily_digest'] = not self.users_data[user_id]['daily_digest']
        self.save_data()
        return self.users_data[user_id]['daily_digest']
    
    async def send_daily_digest(self, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Отправляет ежедневные дайджесты всем пользователям"""
        logger.info("Начинаем отправку ежедневных дайджестов")
        
        for user_id, user_data in self.users_data.items():
            try:
                if not user_data.get('daily_digest', False):
                    continue
                
                topics = user_data.get('topics', [])
                if not topics:
                    continue
                
                digest_message = "📰 <b>Ежедневный дайджест новостей</b>\n\n"
                has_news = False
                
                for topic_data in topics:
                    topic_name = topic_data['name']
                    keywords = topic_data.get('keywords', [])
                    
                    articles = self.get_news(topic_name)
                    if keywords:
                        articles = self.filter_news_by_keywords(articles, keywords)
                    
                    if articles:
                        has_news = True
                        digest_message += self.format_news_message(articles, topic_name)
                        digest_message += "\n" + "="*50 + "\n\n"
                
                if has_news:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=digest_message,
                        parse_mode='HTML',
                        disable_web_page_preview=True
                    )
                    logger.info(f"Отправлен дайджест пользователю {user_id}")
                else:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text="📰 Сегодня новостей по вашим темам не найдено."
                    )
                
                # Обновляем время последнего дайджеста
                self.users_data[user_id]['last_digest'] = datetime.now().isoformat()
                self.save_data()
                
            except Exception as e:
                logger.error(f"Ошибка при отправке дайджеста пользователю {user_id}: {e}")
        
        logger.info("Завершена отправка ежедневных дайджестов")

# Создаем экземпляр бота
news_bot = NewsBot()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start"""
    user_id = update.effective_user.id
    username = update.effective_user.username or "пользователь"
    
    welcome_message = f"""
👋 Привет, {username}!

Я бот для сбора и отправки новостей по интересующим вас темам.

<b>Доступные команды:</b>
/start - Начать работу с ботом
/add_topic - Добавить тему для отслеживания
/remove_topic - Удалить тему
/my_topics - Показать мои темы
/get_news - Получить новости по теме
/digest - Получить дайджест новостей
/toggle_digest - Включить/выключить ежедневные дайджесты
/help - Показать справку

<b>Как использовать:</b>
1. Добавьте интересующие вас темы командой /add_topic
2. При необходимости добавьте ключевые слова для фильтрации
3. Получайте новости командой /get_news или включите ежедневные дайджесты
"""
    
    await update.message.reply_text(welcome_message, parse_mode='HTML')

async def add_topic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /add_topic"""
    user_id = update.effective_user.id
    
    if not context.args:
        await update.message.reply_text(
            "Использование: /add_topic &lt;тема&gt; [ключевые слова через запятую]\n"
            "Пример: /add_topic искусственный интеллект машинное обучение, нейросети"
        )
        return
    
    topic = context.args[0]
    keywords = []
    
    if len(context.args) > 1:
        keywords = [kw.strip() for kw in ' '.join(context.args[1:]).split(',')]
    
    news_bot.add_user_topic(user_id, topic, keywords)
    
    message = f"✅ Тема '{topic}' добавлена!"
    if keywords:
        message += f"\n🔍 Ключевые слова: {', '.join(keywords)}"
    
    await update.message.reply_text(message)

async def remove_topic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /remove_topic"""
    user_id = update.effective_user.id
    
    if not context.args:
        await update.message.reply_text(
            "Использование: /remove_topic &lt;тема&gt;\n"
            "Пример: /remove_topic искусственный интеллект"
        )
        return
    
    topic = ' '.join(context.args)
    
    if news_bot.remove_user_topic(user_id, topic):
        await update.message.reply_text(f"✅ Тема '{topic}' удалена!")
    else:
        await update.message.reply_text(f"❌ Тема '{topic}' не найдена!")

async def my_topics(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /my_topics"""
    user_id = update.effective_user.id
    topics = news_bot.get_user_topics(user_id)
    
    if not topics:
        await update.message.reply_text("📝 У вас пока нет добавленных тем.")
        return
    
    message = "📝 <b>Ваши темы:</b>\n\n"
    for i, topic_data in enumerate(topics, 1):
        topic_name = topic_data['name']
        keywords = topic_data.get('keywords', [])
        added_at = topic_data.get('added_at', '')
        
        message += f"{i}. <b>{topic_name}</b>\n"
        if keywords:
            message += f"   🔍 Ключевые слова: {', '.join(keywords)}\n"
        if added_at:
            try:
                date_obj = datetime.fromisoformat(added_at)
                formatted_date = date_obj.strftime('%d.%m.%Y')
                message += f"   📅 Добавлено: {formatted_date}\n"
            except:
                pass
        message += "\n"
    
    await update.message.reply_text(message, parse_mode='HTML')

async def get_news(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /get_news"""
    user_id = update.effective_user.id
    
    if not context.args:
        await update.message.reply_text(
            "Использование: /get_news &lt;тема&gt;\n"
            "Пример: /get_news искусственный интеллект"
        )
        return
    
    topic = ' '.join(context.args)
    
    # Получаем новости
    articles = news_bot.get_news(topic)
    
    if not articles:
        await update.message.reply_text(f"📰 По теме '{topic}' новостей не найдено.")
        return
    
    # Проверяем, есть ли у пользователя эта тема с ключевыми словами
    user_topics = news_bot.get_user_topics(user_id)
    for topic_data in user_topics:
        if topic_data['name'].lower() == topic.lower():
            keywords = topic_data.get('keywords', [])
            if keywords:
                articles = news_bot.filter_news_by_keywords(articles, keywords)
            break
    
    message = news_bot.format_news_message(articles, topic)
    
    # Разбиваем сообщение на части, если оно слишком длинное
    if len(message) > 4000:
        parts = [message[i:i+4000] for i in range(0, len(message), 4000)]
        for part in parts:
            await update.message.reply_text(part, parse_mode='HTML', disable_web_page_preview=True)
    else:
        await update.message.reply_text(message, parse_mode='HTML', disable_web_page_preview=True)

async def digest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /digest"""
    user_id = update.effective_user.id
    topics = news_bot.get_user_topics(user_id)
    
    if not topics:
        await update.message.reply_text("📝 У вас нет добавленных тем для дайджеста.")
        return
    
    digest_message = "📰 <b>Дайджест новостей</b>\n\n"
    has_news = False
    
    for topic_data in topics:
        topic_name = topic_data['name']
        keywords = topic_data.get('keywords', [])
        
        articles = news_bot.get_news(topic_name)
        if keywords:
            articles = news_bot.filter_news_by_keywords(articles, keywords)
        
        if articles:
            has_news = True
            digest_message += news_bot.format_news_message(articles, topic_name)
            digest_message += "\n" + "="*50 + "\n\n"
    
    if has_news:
        # Разбиваем сообщение на части, если оно слишком длинное
        if len(digest_message) > 4000:
            parts = [digest_message[i:i+4000] for i in range(0, len(digest_message), 4000)]
            for part in parts:
                await update.message.reply_text(part, parse_mode='HTML', disable_web_page_preview=True)
        else:
            await update.message.reply_text(digest_message, parse_mode='HTML', disable_web_page_preview=True)
    else:
        await update.message.reply_text("📰 Сегодня новостей по вашим темам не найдено.")

async def toggle_digest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /toggle_digest"""
    user_id = update.effective_user.id
    is_enabled = news_bot.toggle_daily_digest(user_id)
    
    status = "включены" if is_enabled else "выключены"
    await update.message.reply_text(f"📅 Ежедневные дайджесты {status}!")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /help"""
    help_text = """
📖 <b>Справка по командам:</b>

<b>Основные команды:</b>
/start - Начать работу с ботом
/help - Показать эту справку

<b>Управление темами:</b>
/add_topic &lt;тема&gt; [ключевые слова] - Добавить тему для отслеживания
/remove_topic &lt;тема&gt; - Удалить тему
/my_topics - Показать все ваши темы

<b>Получение новостей:</b>
/get_news &lt;тема&gt; - Получить новости по конкретной теме
/digest - Получить дайджест по всем вашим темам

<b>Настройки:</b>
/toggle_digest - Включить/выключить ежедневные дайджесты

<b>Примеры использования:</b>
/add_topic искусственный интеллект машинное обучение, нейросети
/get_news программирование
/digest

<b>Примечание:</b>
Для работы с новостями необходим API ключ NewsAPI. 
Без него бот будет показывать только заглушки.
"""
    
    await update.message.reply_text(help_text, parse_mode='HTML')

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик ошибок"""
    logger.error(f"Ошибка при обработке обновления: {context.error}")
    
    if update and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "❌ Произошла ошибка. Попробуйте позже или обратитесь к администратору."
            )
        except Exception as e:
            logger.error(f"Не удалось отправить сообщение об ошибке: {e}")

def main() -> None:
    """Основная функция для запуска бота"""
    # Получаем токен бота из переменных окружения
    bot_token = os.getenv('BOT_TOKEN')
    
    if not bot_token:
        logger.error("BOT_TOKEN не найден в переменных окружения!")
        return
    
    # Создаем приложение
    application = Application.builder().token(bot_token).build()
    
    # Добавляем обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("add_topic", add_topic))
    application.add_handler(CommandHandler("remove_topic", remove_topic))
    application.add_handler(CommandHandler("my_topics", my_topics))
    application.add_handler(CommandHandler("get_news", get_news))
    application.add_handler(CommandHandler("digest", digest))
    application.add_handler(CommandHandler("toggle_digest", toggle_digest))
    application.add_handler(CommandHandler("help", help_command))
    
    # Добавляем обработчик ошибок
    application.add_error_handler(error_handler)
    
    # Настраиваем ежедневные дайджесты (каждый день в 9:00)
    job_queue = application.job_queue
    job_queue.run_daily(
        news_bot.send_daily_digest,
        time=datetime.strptime("09:00", "%H:%M").time(),
        name="daily_digest"
    )
    
    logger.info("Бот запущен!")
    
    # Запускаем бота
    application.run_polling()

if __name__ == '__main__':
    main()

