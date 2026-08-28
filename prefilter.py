import re

import config

_COMPILED_PATTERNS = [re.compile(pattern, re.IGNORECASE) for pattern in config.DEMAND_KEYWORDS]


def is_demand_intent(text: str) -> bool:
    if not text:
        return False
    return any(pattern.search(text) for pattern in _COMPILED_PATTERNS)
