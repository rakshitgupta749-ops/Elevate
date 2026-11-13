import re
import logging

logger = logging.getLogger(__name__)

from typing import Tuple, Optional
import re
import logging

logger = logging.getLogger(__name__)

# Enterprise input validation rules
FORBIDDEN_JAILBREAK_PATTERNS = [
    (r"(?i)\bignore\s+(all\s+)?(previous|prior|above)\s+(instructions|prompts|rules|commands|directives)\b", "ignore previous instructions"),
    (r"(?i)\b(reveal|show|print|output|display|repeat|leak|dump|give\s+me)\s+(your\s+)?(system\s+prompt|system\s+instructions|initial\s+prompt)\b", "reveal system prompt"),
    (r"(?i)\bwhat\s+(is|was)\s+your\s+(system\s+prompt|initial\s+prompt|system\s+instruction)\b", "request system prompt"),
    (r"(?i)\byou\s+are\s+now\s+(an?\s+)?(unrestricted|dan|jailbreak|evil|hacker|bot|developer mode|virtual machine|unfiltered|bypassed)\b", "jailbreak persona adoption"),
    (r"(?i)\byou\s+are\s+now\s+free\s+from\s+(all\s+)?(rules|restrictions|constraints)\b", "jailbreak restriction bypass"),
    (r"(?i)\bbypass\s+(all\s+)?(restrictions|guardrails|safety|rules|filters)\b", "bypass restrictions"),
    (r"(?i)\bforget\s+(all\s+)?(previous|prior)\s+(instructions|context|rules|conversations)\b", "forget previous instructions"),
    (r"(?i)\bact\s+as\s+a\s+(hacker|jailbreaker|unrestricted\s+ai|dan)\b", "act as hacker/jailbreaker"),
]

TOXIC_WORDS = [
    "fuck", "shit", "bitch", "asshole", "cunt", "nigger", "faggot"
]

def validate_input(text: str) -> Tuple[bool, Optional[str]]:
    """
    Enterprise-grade guardrails for input validation.
    Returns (True, None) if safe, or (False, reason_message) if rejected.
    """
    if not text or not text.strip():
        return False, "Input message cannot be empty."

    # Allow detailed executive interview candidate answers up to 15,000 characters (~2,500 words)
    if len(text) > 15000:
        logger.warning(f"Guardrail triggered: Input length ({len(text)} chars) exceeds maximum allowed limit (15000 chars).")
        return False, f"Your response exceeds the length limit (received {len(text):,} characters; maximum allowed is 15,000 characters). Please shorten your answer."

    for pattern, description in FORBIDDEN_JAILBREAK_PATTERNS:
        if re.search(pattern, text):
            logger.warning(f"Guardrail triggered: Jailbreak pattern detected ({description}).")
            return False, f"Your response was flagged by safety guidelines ({description}). Please rephrase your answer."

    text_lower = text.lower()
    for word in TOXIC_WORDS:
        # Match whole word to avoid false positives on benign words containing substrings
        if re.search(rf"\b{re.escape(word)}\b", text_lower):
            logger.warning(f"Guardrail triggered: Toxic language detected ({word}).")
            return False, "Your response contains language flagged by professional communication standards. Please rephrase your answer."

    return True, None

def is_safe_input(text: str) -> bool:
    """Enterprise-grade guardrails for input validation (backward-compatible boolean check)."""
    is_safe, _ = validate_input(text)
    return is_safe

def sanitize_output(text: str) -> str:
    """Sanitize AI output to prevent PII leakage and format tokens."""
    # Remove internal instruction tags if any leak
    text = re.sub(r'\[.*?\]', '', text)
    # Remove excessive whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def is_candidate_exit_intent(text: str) -> bool:
    """Detect if the candidate is requesting to end, quit, or leave the interview prematurely."""
    if not text:
        return False

    cleaned = text.strip()
    exit_patterns = [
        r"(?i)\b(end|stop|cancel|quit|finish)\s+(this|the)?\s*(session|interview|meeting|call)\b",
        r"(?i)\b(can\s+you|please|let's|lets)\s+(end|stop|wrap\s+up)\s+(this|the)?\s*(session|interview|meeting|call)?\b",
        r"(?i)\bi\s+(want|need|have|got)\s+to\s+(go|leave|end|stop|quit)\b",
        r"(?i)\bi\s+have\s+(some\s+)?(urgent\s+)?(work|meeting|call|emergency)\b",
        r"(?i)\bi\s+can't\s+continue\b",
        r"(?i)\bhave\s+to\s+run\b",
        r"(?i)\bwrap\s+up\s+now\b",
        r"(?i)\bend\s+now\b",
        r"(?i)\blet's\s+cut\s+it\s+short\b",
    ]
    for pattern in exit_patterns:
        if re.search(pattern, cleaned):
            return True
    return False

