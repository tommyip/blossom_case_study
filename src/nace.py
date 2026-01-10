NACE_CATEGORIES = {
    "62": "Software & IT",
    "63": "Data & Hosting",
    "58": "Software Publishing",
    "64": "Financial Services",
    "66": "FinTech Support",
    "21": "Pharma & Biotech",
    "72": "R&D",
    "26": "Electronics & Hardware",
    "70": "Consulting",
    "73": "Marketing & Advertising",
    "61": "Telecommunications",
    "46": "Wholesale Trade",
    "47": "Retail Trade",
    "41": "Construction",
    "68": "Real Estate",
    "69": "Legal & Accounting",
    "74": "Professional Services",
    "85": "Education",
    "86": "Health",
}

TECH_NACE_PREFIXES = ["62", "63", "58", "64", "66", "21", "72", "26", "61"]


def _normalize_code(code: float | str | None) -> str | None:
    if code is None:
        return None
    if isinstance(code, float):
        code = str(int(code))
    return str(code).strip()


def get_nace_category(code: float | str | None) -> str:
    code = _normalize_code(code)
    if not code:
        return "Unknown"

    # Try exact 2-digit prefix match
    prefix = code[:2]
    if prefix in NACE_CATEGORIES:
        return NACE_CATEGORIES[prefix]

    return "Other"


def is_tech_company(code: float | str | None) -> bool:
    code = _normalize_code(code)
    if not code:
        return False

    prefix = code[:2]
    return prefix in TECH_NACE_PREFIXES
