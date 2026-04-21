import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: str = os.environ["BOT_TOKEN"]
CHANNEL_ID: str = os.environ["CHANNEL_ID"]

# Resolve relative sqlite paths to absolute (safe regardless of cwd)
_HERE = os.path.dirname(os.path.abspath(__file__))
_raw_db = os.getenv("DATABASE_URL", "sqlite:///semenabot.db")
if _raw_db.startswith("sqlite:///") and not _raw_db.startswith("sqlite:////"):
    _rel = _raw_db[len("sqlite:///"):]
    if not os.path.isabs(_rel):
        _raw_db = f"sqlite:///{os.path.join(_HERE, _rel)}"
DATABASE_URL: str = _raw_db
MIN_PRICE: int = int(os.getenv("MIN_PRICE", "100000"))

# Keywords used for SEARCHING on each platform
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
        "посевной материал овощ",
    ],
    "grasses": [
        "семена трав",
        "семена кормовых",
        "семена клевер",
        "семена люцерн",
        "семена тимофеевка",
        "семена овсяниц",
        "газонные семена",
        "семена газонных",
        "посевной материал трав",
    ],
}

ROSELTORG_PROXY: str = os.getenv(
    "ROSELTORG_PROXY",
    "http://yq3MUmtH:BqzN3LAa@195.208.89.54:64310",
)

# Post-fetch whitelist: title MUST contain at least one of these (case-insensitive)
# "семен" covers: семена, семенной, семенного, семенам...
# "семян" covers: семян, семянной... (genitive plural used in "поставка семян X")
REQUIRE_KEYWORDS: list[str] = [
    "семен",   # семена, семенной, семенного...
    "семян",   # семян (genitive plural: "поставка семян клевера")
    "посевн",  # посевной материал, посевная
]

# Post-fetch blacklist: title must NOT contain any of these
EXCLUDE_KEYWORDS: list[str] = [
    "рассад",        # рассада, рассады, рассадный
    "саженц",        # саженцы, саженцев
    "черенк",        # черенки
    "подсолнечник",
    "семейн",        # семейный, семейного, семейного центра
    "семьи",
    "семья",
]
