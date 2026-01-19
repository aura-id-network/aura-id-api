import os
from pathlib import Path
from dotenv import load_dotenv

# Загрузка переменных окружения
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

# СЕКРЕТНЫЕ ДАННЫЕ БЕРЕМ ИЗ ПЕРЕМЕННЫХ ОКРУЖЕНИЯ
# Если переменных нет, используем заглушки или пустые значения
BOT_TOKEN = os.getenv("BOT_TOKEN", "your_bot_token_here")

# Обработка списка админов из строки "123,456"
admin_ids_str = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = [int(x) for x in admin_ids_str.split(",") if x.strip().isdigit()]

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///aura_pro.db")

CARD_CREATION_PRICE = 1  # Telegram Stars

ENGRAVING_COLORS = {
    "white": "#FFFFFF",
    "bronze": "#CD7F32", 
    "gold": "#FFD700"
}

# Настройки API
FLASK_HOST = os.getenv("FLASK_HOST", "0.0.0.0")
FLASK_PORT = int(os.getenv("FLASK_PORT", 20196))
API_BASE_URL = os.getenv("API_BASE_URL", "https://144.31.164.141.sslip.io")

# Пути к сервисам 
SERVICE_DIR = os.getenv("SERVICE_DIR", "/root/aurabot") # Можно заменить на свой путьк проекту  
PID_DIR = os.getenv("PID_DIR", os.path.join(SERVICE_DIR, "pids"))
LOG_DIR = os.getenv("LOG_DIR", os.path.join(SERVICE_DIR, "logs"))
