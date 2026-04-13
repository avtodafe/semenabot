import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: str = os.environ["BOT_TOKEN"]
CHANNEL_ID: str = os.environ["CHANNEL_ID"]
DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///semenabot.db")
MIN_PRICE: int = int(os.getenv("MIN_PRICE", "500000"))

# Keywords by group — OR logic within each group
KEYWORD_GROUPS: dict[str, list[str]] = {
    "vegetables": [
        "семена овощ",
        "семена томат",
        "семена огурец",
        "семена перец",
        "семена капуста",
        "семена свёкла",
        "семена морковь",
        "семена лук",
        "семена кабачок",
        "рассада",
        "посевной материал овощ",
    ],
    "grasses": [
        "семена трав",
        "кормовые травы",
        "семена клевер",
        "семена люцерн",
        "семена тимофеевка",
        "семена овсяниц",
        "сенокосный травостой",
        "газонные семена",
        "посевной материал трав",
    ],
    "seedlings": [
        "саженцы",
        "посадочный материал",
        "черенки",
        "рассада многолетн",
    ],
}

EXCLUDE_KEYWORDS: list[str] = [
    "семена подсолнечник",
]
