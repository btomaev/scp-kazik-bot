from datetime import timedelta
from os import getenv
from typing import Any

from dotenv import load_dotenv
from yaml import safe_load


load_dotenv()

CONFIG_PATH = 'config.yml'

BOT_TOKEN = getenv('TELEGRAM_API_TOKEN') or ''
DEBUG = getenv('DEBUG', 'false').strip().lower() in {'1', 'true', 'yes', 'on'}
DATABASE_URL = getenv(
    'DATABASE_URL',
    'sqlite+aiosqlite:///data/bot.db',
)

assert BOT_TOKEN

with open(CONFIG_PATH, encoding='utf-8') as file:
    _config = safe_load(file)


def extract_period(param: dict[str, int]) -> timedelta:
    return timedelta(
        minutes=param.get('minutes', 0),
        hours=param.get('hours', 0),
        days=param.get('days', 0),
        weeks=param.get('weeks', 0),
    )


def get(param: str, default: Any = None) -> Any:
    params = param.split('.')
    current_layer = _config

    for name in params:
        if name in current_layer:
            current_layer = current_layer[name]
        else:
            return default

    return current_layer
