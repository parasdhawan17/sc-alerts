"""Map merchants to spending categories."""

import re
from typing import Optional

# Icons displayed in front of category names on the sheet.
CATEGORY_ICONS = {
    "Rent": "🏠",
    "Groceries": "🛒",
    "Eating Out": "🍽️",
    "Online Delivery": "📦",
    "Taxi": "🚕",
    "Public Transport": "🚌",
    "Medical": "🏥",
    "Clothes Shopping": "👕",
    "Trips": "✈️",
    "Entertainment": "🎬",
    "Fitness": "🏋️",
    "Subscriptions": "📺",
    "Utils": "💡",
    "Home": "🏡",
    "Government": "🏛️",
    "Investment": "📈",
    "Remittance": "💸",
    "Personal Transfer": "🔄",
    "PayNow": "📲",
    "Other": "❓",
}


_LEGACY_CATEGORY_MAP = {
    "Family": "PayNow",
    "👨‍👩‍👧‍👦 Family": "PayNow",
}


def normalize_category(category: str) -> str:
    """Map legacy/removed category names to their current replacements."""
    return _LEGACY_CATEGORY_MAP.get(category, category)

# Display order on month tabs (categories with zero spend are omitted).
CATEGORY_ORDER = [
    "Rent",
    "Groceries",
    "Eating Out",
    "PayNow",
    "Online Delivery",
    "Taxi",
    "Public Transport",
    "Medical",
    "Clothes Shopping",
    "Trips",
    "Entertainment",
    "Fitness",
    "Subscriptions",
    "Utils",
    "Home",
    "Government",
    "Investment",
    "Remittance",
    "Personal Transfer",
    "Other",
]


def display_category(category: str) -> str:
    """Return category name with its icon prefix for display in the sheet."""
    category = normalize_category(category)
    icon = CATEGORY_ICONS.get(category, "")
    return f"{icon} {category}" if icon else category


_PAYNOW_PATTERN = re.compile(r"\(MOBILE ending \d+\)", re.I)


def is_paynow_merchant(merchant: str) -> bool:
    """Return True for merchants that look like mobile/PayNow transfers."""
    return bool(_PAYNOW_PATTERN.search(merchant))


# Merchants excluded from category totals (e.g. credit card bill payments).
EXCLUDED_MERCHANTS = {
    "DBS Altitude Visa Signature Card (Ref ending 7227)",
}

# Exact merchant name → category.
EXACT_CATEGORIES: dict[str, str] = {
    "Loh Hui Xian A/C ending 3073": "Rent",
    "Anisha (MOBILE ending 8680)": "PayNow",
    "AniXXX (MOBILE ending 8680)": "PayNow",
    "jc0011 (MOBILE ending 3066)": "PayNow",
    "karen sim (MOBILE ending 3958)": "PayNow",
    "Mehal (MOBILE ending 8612)": "PayNow",
    "Huixuan (MOBILE ending 2916)": "PayNow",
    "Kasturi (MOBILE ending 0516)": "PayNow",
    "Choo (MOBILE ending 6123)": "PayNow",
    "VIBRANCE (MOBILE ending 9078)": "PayNow",
    "Lustrelite Store (MOBILE ending 0300)": "PayNow",
    "PAYNOW - SUPPORTED BY 2C2P PTE LTD (UEN ending C002)": "PayNow",
    "NIUM PTE. LTD. -CUSTOMERS' ACCOUNT (UEN ending R001)": "Remittance",
    "WOTRANSFER PTE. LTD. (UEN ending 244H)": "Remittance",
    "REVOLUT TECHNOLOGIES SINGAPORE PTE. LTD. (UEN ending 013G)": "Remittance",
    "SYFE PTE. LTD. (UEN ending HATS)": "Investment",
    "AISG INVESTMENT HOLDING PTE. LTD. (UEN ending HLZD)": "Investment",
    "COMFORT TAXI": "Taxi",
    "WWW.TADA.GLOB": "Taxi",
    "BUS/MRT": "Public Transport",
    "SIMPLYGO SBST": "Public Transport",
    "TRANSIT": "Public Transport",
    "www.anywheel": "Public Transport",
    "HELLORIDE_SG": "Public Transport",
    "PARKWAY MEDIC": "Medical",
    "POTONG PASIR MEDICAL C": "Medical",
    "POTONG PASIR MEDICAL CLINIC PTE. LTD. (UEN ending NPP1)": "Medical",
    "INTEMEDICAL P": "Medical",
    "TRUECARE CLINIC": "Medical",
    "WATSONS - THE": "Medical",
    "GUARDIAN WOOD": "Medical",
    "GUARDIAN CITY": "Medical",
    "GUARDIAN THE": "Medical",
    "FLYSCOOT.COM": "Trips",
    "VIETJET AIR CURRENCY": "Trips",
    "VietJet": "Trips",
    "MakeMyTrip": "Trips",
    "STARHUB LTD (UEN ending CSHL)": "Utils",
    "STARHUB RECUR": "Utils",
    "SP SERVICES LTD (UEN ending NQ1M)": "Utils",
    "ICLEANER PTE. LTD. (UEN ending 690R)": "Home",
    "MINISTRY OF MANPOWER (UEN ending CFWL)": "Government",
    "MINISTRY OF MANPOWER (UEN ending CMDW)": "Government",
    "IMMIGRATION & CHECKPOINTS AUTHORITY /AG (UEN ending DI3A)": "Government",
    "LINK.COM* CERTIVERSE": "Government",
    "Harry Potter": "Entertainment",
    "LOST SG": "Entertainment",
    "SENTOSA EXPRESS": "Entertainment",
    "PS": "Entertainment",
    "PURE YOGA NAC": "Fitness",
    "CURSOR, AI POWERED IDE": "Subscriptions",
    "CURSOR USAGE MID MAR": "Subscriptions",
    "CURSOR USAGE MAR": "Subscriptions",
    "OPENAI": "Subscriptions",
    "AI KIT PTE LT": "Subscriptions",
    "YOU TECHNOLOGIES GROUP PL - CUST ACC (UEN ending CDB2)": "Subscriptions",
    "SHOPEEPAY PRIVATE LIMITED (UEN ending CSMP)": "Online Delivery",
    "SHOPEE SG MP": "Online Delivery",
    "SHOPEE SINGAPORE MP": "Online Delivery",
    "SHOPEE APPLEP": "Online Delivery",
    "Lazada": "Online Delivery",
    "GET*GET*Mr Bi": "Online Delivery",
    "Now Pizza Gat": "Online Delivery",
    "ASICS": "Clothes Shopping",
    "ASICS - PLAZA": "Clothes Shopping",
    "PULL & BEAR-V": "Clothes Shopping",
    "COTTON ON SIN": "Clothes Shopping",
    "ZARA - VIVOCI": "Clothes Shopping",
    "UNIQLO PLAZA": "Clothes Shopping",
    "SEPHORA-PS": "Clothes Shopping",
    "SHOP SASSY DR": "Clothes Shopping",
    "KIDDY PALACE": "Clothes Shopping",
    "DAISO JAPAN -": "Clothes Shopping",
    "DAISO JAPAN - PS": "Clothes Shopping",
    "SCARLETT-TREN": "Clothes Shopping",
    "M & S - PLAZA": "Clothes Shopping",
    "NTUC FairPric": "Groceries",
    "NTUC Fairpric": "Groceries",
    "NTUC FP - POI": "Groceries",
    "NTUC FP - POIZ": "Groceries",
    "FAIRPRICE FIN": "Groceries",
    "FP XTRA VIVO": "Groceries",
    "COLD STORAGE-": "Groceries",
    "SHENG SIONG S": "Groceries",
    "SHENG SIONG SUPERMARKE": "Groceries",
    "HAO MART - PO": "Groceries",
    "ABC BARGAIN CENTR": "Groceries",
    "MOHAMED MUSTAFA & SAM-": "Groceries",
    "PONNI INDIAN GROCERIES PTE LTD (UEN ending 500W)": "Groceries",
    "PONNI INDIAN GROCERIES PTE. LTD. (UEN ending WNXT)": "Groceries",
    "PRINCE FRUITS (UEN ending 923C)": "Groceries",
    "PRO-DEO TRADING": "Groceries",
    "MINAKA TRADING PTE. LTD. (UEN ending CDBS)": "Groceries",
    "J R IMPORT & EXPORT (S) PTE. LTD. (UEN ending RB33)": "Groceries",
    "JAI & JAI TRADING PTE LTD (UEN ending 689W)": "Groceries",
    "ANG MO SUPERM": "Groceries",
    "CS FRESH LENT": "Groceries",
}

# (pattern, category) — first match wins. Patterns are case-insensitive regex.
PATTERN_CATEGORIES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\(MOBILE ending \d+\)", re.I), "PayNow"),
    (re.compile(r"^Grab\*", re.I), "Taxi"),
    (re.compile(r"^NTUC", re.I), "Groceries"),
    (re.compile(r"^FAIRPRICE", re.I), "Groceries"),
    (re.compile(r"^FP XTRA", re.I), "Groceries"),
    (re.compile(r"^COLD STORAGE", re.I), "Groceries"),
    (re.compile(r"^SHENG SIONG", re.I), "Groceries"),
    (re.compile(r"^HAO MART", re.I), "Groceries"),
    (re.compile(r"^GUARDIAN", re.I), "Medical"),
    (re.compile(r"^WATSONS", re.I), "Medical"),
    (re.compile(r"^SHOPEE", re.I), "Online Delivery"),
    (re.compile(r"^POTONG PASIR MEDICAL", re.I), "Medical"),
    (re.compile(r"^Qashier-", re.I), "Eating Out"),
    (re.compile(r"^FNB_USS_", re.I), "Eating Out"),
    (re.compile(r"^MCDONALD", re.I), "Eating Out"),
    (re.compile(r"^BURGER KING", re.I), "Eating Out"),
    (re.compile(r"^KFC ", re.I), "Eating Out"),
    (re.compile(r"^WOK ?HEY", re.I), "Eating Out"),
    (re.compile(r"^STARBUCKS", re.I), "Eating Out"),
    (re.compile(r"^BREADTALK", re.I), "Eating Out"),
    (re.compile(r"^AUNTIE ANNE", re.I), "Eating Out"),
    (re.compile(r"^OLD CHANG KEE", re.I), "Eating Out"),
    (re.compile(r"^GENKI SUSHI", re.I), "Eating Out"),
    (re.compile(r"^SUSHI GOGO", re.I), "Eating Out"),
    (re.compile(r"^KOPITIAM", re.I), "Eating Out"),
    (re.compile(r"^7-ELEVEN", re.I), "Eating Out"),
    (re.compile(r"^FR VIVO", re.I), "Eating Out"),
    (re.compile(r"^SMP\*", re.I), "Eating Out"),
    (re.compile(r"^MR\.?\s*COCONUT", re.I), "Eating Out"),
    (re.compile(r"^TORI-Q", re.I), "Eating Out"),
    (re.compile(r"^DAISO JAPAN", re.I), "Clothes Shopping"),
    (re.compile(r"^CURSOR", re.I), "Subscriptions"),
    (re.compile(r"^STARHUB", re.I), "Utils"),
    (re.compile(r"^MINISTRY OF MANPOWER", re.I), "Government"),
    (re.compile(r"^IMMIGRATION & CHECKPOINTS", re.I), "Government"),
]

# Known eating-out merchants (hawker, restaurants, cafés, food courts).
EATING_OUT_MERCHANTS = {
    "DIN TAI FUNG",
    "SAIZERIYA - P",
    "NANDO'S",
    "Guzman y Gome",
    "Kopitiam Inve",
    "THE COFFEE BE",
    "STARBUCKS@PLZ",
    "OLD HEN KITCH",
    "Marche",
    "EMICAKES",
    "XW WESTERN GR",
    "BULGOGI SYO -",
    "KAARLA & OUMI",
    "DELHI 6_RACE",
    "SWEE HENG BAK",
    "SWEE HENG",
    "THE GREEN PAR",
    "YoChi Asia Pt",
    "GENKI SUSHI-V",
    "GET*GET*Mr Bi",
    "RASAPURA MAST",
    "NICE2MEETU",
    "MOM'S HAND MI",
    "Random Foods SP",
    "ORICHI",
    "The Gula Lab",
    "Shawarma Shac",
    "RISEBAKEHOUSE",
    "STUFF'D WOODL",
    "STUFF'D VIVOC",
    "YA KUN KAYA T",
    "IJOOZ AI PTE",
    "Burger King",
    "MCDONALD'S (P",
    "MCDONALD'S (W",
    "WOKHEY @ PLAZ",
    "WOK HEY - PLAZA SINGAP",
    "WOKHEY-WOODLE",
    "WOK HEY Woodl",
    "WOK HEY - NEX",
    "NIKUIKU-TWM",
    "CNCTTNHH AUTOGRILLVFSF",
    "DABBA STREET",
    "JURASSIC NEST-GBB(F&B)",
    "M Burger Inn",
    "KOPITIAM@PLAZA SINGAPU",
    "BJB-PlazaSing",
    "OTTER PIZZA PTE. LTD. (UEN ending HPC1)",
    "JAGGIS",
    "OLD CHANG KEE",
    "POPULAR BOOK",
    "NET*TIME FOR",
    "YOLE PLAZA SI",
    "POLAR PUFFS &",
    "KOPI & TARTS",
    "ANANDA BHAVAN RESTAURANT (UEN ending MCAT)",
    "HONG KONG EGG",
    "FOMO PAY PTE. LTD. (UEN ending D002)",
    "CHINATOWN TAN'S TUTU C",
    "MUNCHI PS PTE",
    "MIXUE",
    "O BREAD 2 PTE. LTD. (UEN ending 081K)",
    "ORCHID CHOPST",
    "ORCHID CHOPSTICKS_TREN",
    "CHUAN MERCHANDISING",
    "KARTHIKA ENTERPRI",
    "Beard Papa's",
    "PAWA CATERING",
    "Ezy Vending P",
    "IBOOZEESG",
    "TEZZSOLUTION SG PTE. LTD. (UEN ending 402K)",
    "KIK CONSULTS PTE. LTD. (UEN ending 068M)",
    "YAMAHA MUSIC-",
}


def is_excluded_merchant(merchant: str) -> bool:
    return merchant.strip() in EXCLUDED_MERCHANTS


def categorize_merchant(merchant: str) -> Optional[str]:
    """Return display category for merchant, or None if excluded from tracking."""
    name = merchant.strip()
    if not name or is_excluded_merchant(name):
        return None

    if name in EXACT_CATEGORIES:
        return display_category(EXACT_CATEGORIES[name])

    if name in EATING_OUT_MERCHANTS:
        return display_category("Eating Out")

    for pattern, category in PATTERN_CATEGORIES:
        if pattern.search(name):
            return display_category(category)

    return display_category("Other")


def aggregate_by_category(merchant_rows: list[dict]) -> list[dict]:
    """Sum merchant rows into category totals, preserving CATEGORY_ORDER.

    Rows marked include=False are excluded. If a row has an explicit category,
    that category is used; otherwise the merchant is categorized automatically.
    """
    totals: dict[str, float] = {}
    for row in merchant_rows:
        if not row.get("include", True):
            continue
        category = row.get("category")
        if not category:
            category = categorize_merchant(row["merchant"])
        if category is None:
            continue
        totals[category] = totals.get(category, 0.0) + row["total"]

    display_order = [display_category(category) for category in CATEGORY_ORDER]
    rows = [
        {"category": category, "total": totals[category]}
        for category in display_order
        if category in totals and totals[category] > 0
    ]
    return rows
