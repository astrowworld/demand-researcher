import os

DB_PATH = os.environ.get("DEMAND_RESEARCHER_DB", "demand_researcher.db")
TARGETED_SUBS = ["forhire", "slavelabour"]
CLAUDE_MODEL = "claude-haiku-4-5-20251001"

DEMAND_KEYWORDS = [
    r"\bcherche\b",
    r"\brecherch(e|es|ons)\b",
    r"\bISO\b",
    r"\bWTB\b",
    r"looking for",
    r"where (can|do) i (find|buy)",
    r"need a (dev|developer|freelance|freelancer)",
    r"anyone (know|selling)",
    r"want to buy",
    r"\bà la recherche\b",
    r"quelqu'un (a|aurait)",
]
