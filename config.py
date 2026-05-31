import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
LOGO_PATH = BASE_DIR / "assets" / "logo.jpg"
LOGO_PNG_PATH = BASE_DIR / "assets" / "logo.png"


def load_env_file():
    """Читает .env и загружает настройки подключения к PostgreSQL."""
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env_file()

# Настройки PostgreSQL. Обычно меняют только PG_PORT и PG_DATABASE.
PG_HOST = os.getenv("PG_HOST", "localhost")
PG_PORT = int(os.getenv("PG_PORT", "5432"))
PG_DATABASE = os.getenv("PG_DATABASE", "green_garden")
PG_USER = os.getenv("PG_USER", "postgres")
PG_PASSWORD = os.getenv("PG_PASSWORD", "1")

# Цвета интерфейса. Если поменяется бренд/логотип, начать проще отсюда.
GREEN = "#22C55E"
BROWN = "#8B7355"
YELLOW = "#FCD34D"
BG = "#F8FAF5"
DARK = "#1F3D2B"

# Системные значения типов товара и их русские подписи в интерфейсе.
TYPE_NAMES = {
    "seed": "Семена",
    "seedling": "Рассада",
    "plant": "Растение",
    "bulb": "Луковица",
}

# Системные значения статусов заказа и их русские подписи.
STATUS_NAMES = {
    "new": "Новый",
    "processing": "В обработке",
    "shipped": "Отправлен",
    "completed": "Завершён",
    "cancelled": "Отменён",
}
