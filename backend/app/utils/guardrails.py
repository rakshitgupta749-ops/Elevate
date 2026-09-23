import re
import logging

logger = logging.getLogger(__name__)

def is_safe_input(text: str) -> bool:
    """Enterprise-grade guardrails for input validation."""
    if not text or len(text) > 2000:
        return False
        
    forbidden_patterns = [
        r"(?i)ignore\s+(all\s+)?previous\s+instructions",
        r"(?i)system\s+prompt",
        r"(?i)you\s+are\s+now",
        r"(?i)bypass\s+restrictions",
        r"(?i)forget\s+everything",
        r"(?i)act\s+as\s+a\s+(hacker|jailbreaker)",
    ]
    
    toxic_words = ["fuck", "shit", "bitch", "asshole", "cunt", "nigger", "faggot"]
    
    text_lower = text.lower()
    
    for pattern in forbidden_patterns:
        if re.search(pattern, text):
            logger.warning(f"Guardrail triggered: Jailbreak pattern detected.")
            return False
            
    for word in toxic_words:
        if word in text_lower:
            logger.warning(f"Guardrail triggered: Toxic language detected.")
            return False
            
    return True

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

