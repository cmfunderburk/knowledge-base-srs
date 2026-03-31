"""Letter-level masking algorithm for generation cards.

Provides three public functions:
- is_maskable(word)   — True if the word is eligible for masking
- mask_word(word, level, seed) — masks letters in a single word
- mask_text(text, level, card_id) — masks eligible words in a text string
"""
import hashlib
import re

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FUNCTION_WORDS: frozenset[str] = frozenset(
    {
        "a", "an", "the",
        "and", "but", "or", "nor", "so", "yet", "for",
        "in", "on", "at", "to", "by", "up", "as", "of",
        "is", "are", "was", "were", "be", "been", "being",
        "it", "its", "it's",
        "that", "this", "these", "those",
        "with", "from", "into", "onto", "upon", "than",
        "not", "no",
        "he", "she", "we", "they", "you", "I",
        "his", "her", "our", "your", "my", "their",
        "who", "which", "when", "where", "how", "if",
        "also", "both", "each", "all", "any", "few",
        "more", "most", "such", "only", "then", "than",
        "has", "have", "had", "do", "does", "did",
        "can", "may", "might", "will", "would", "should", "could",
        "about", "after", "before", "between", "through",
        "over", "under", "per",
    }
)

# Matches numeric tokens: digits, percentages, ranges like 1-year, year spans, etc.
_NUM_RE = re.compile(
    r"""
    ^
    (?:
        \d[\d,.\-/]*%?   # plain numbers, decimals, ranges, with optional %
        | \d+[a-zA-Z\-]+  # numbers with units/suffixes like "1-year", "10yr"
    )
    $
    """,
    re.VERBOSE,
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def is_maskable(word: str) -> bool:
    """Return True if *word* is eligible for masking.

    Not maskable:
    - Function words (case-insensitive lookup)
    - Words of 3 characters or fewer
    - Numeric / numeric-expression tokens (digits, %, ranges)
    - Acronyms: all uppercase and at least 2 characters
    """
    # Short words (≤3 chars) are not maskable
    if len(word) <= 3:
        return False

    # Function words (case-insensitive)
    if word.lower() in FUNCTION_WORDS:
        return False

    # Numeric expressions (strip trailing punctuation for the test)
    stripped = word.rstrip(".,;:!?)")
    if _NUM_RE.match(stripped):
        return False

    # Acronyms: all letters are uppercase and ≥2 chars
    # Strip trailing punctuation before testing
    letters_only = re.sub(r"[^A-Za-z]", "", stripped)
    if letters_only and letters_only == letters_only.upper() and len(letters_only) >= 2:
        return False

    return True


def mask_word(word: str, level: int, seed: int) -> str:
    """Mask letters in *word* according to *level*.

    Rules:
    - Words of ≤3 chars are returned unchanged.
    - The first letter is always preserved.
    - Level 2: all letters after the first are replaced with '_'.
    - Level 0: ~30% of non-first letters masked, no consecutive underscores.
    - Level 1: ~60% of non-first letters masked, no consecutive underscores.
    - Masking is deterministic for a given (word, level, seed) triple.

    Non-letter characters (e.g. trailing punctuation as part of the token)
    are treated as regular positions — they can be masked or kept as letters.
    In practice, mask_text strips punctuation before passing tokens here, so
    this mostly affects trailing punctuation-free words.
    """
    if len(word) <= 3:
        return word

    if level == 2:
        return word[0] + "_" * (len(word) - 1)

    # Determine mask probability
    prob = 0.30 if level == 0 else 0.60

    # Build a per-character mask using the seed
    # We derive a uniform float for each position deterministically
    non_first = list(word[1:])
    n = len(non_first)

    # Generate per-character random values deterministically
    rand_vals = [_uniform(seed, i) for i in range(n)]

    # Apply masking with no-consecutive-underscore constraint
    masked = list(non_first)
    prev_masked = False
    for i in range(n):
        if rand_vals[i] < prob:
            if prev_masked:
                # Skip to avoid consecutive underscores — try the next slot
                masked[i] = non_first[i]
                prev_masked = False
            else:
                masked[i] = "_"
                prev_masked = True
        else:
            masked[i] = non_first[i]
            prev_masked = False

    return word[0] + "".join(masked)


def mask_text(text: str, level: int, card_id: str) -> str:
    """Mask eligible words in *text*.

    - Function words, short words, numbers, and acronyms are preserved.
    - Punctuation attached to words is preserved (stripped for eligibility
      test, re-attached afterwards).
    - Deterministic: uses card_id + level + word_index as the seed base.
    - Empty string returns empty string.
    """
    if not text:
        return text

    # Tokenise preserving whitespace structure.
    # Split on whitespace, keeping track of surrounding whitespace is not
    # required — we just rejoin with single spaces.  Preserve trailing/leading
    # whitespace by checking text itself.
    tokens = text.split()
    result_tokens = []

    for idx, token in enumerate(tokens):
        # Separate leading/trailing punctuation from the word core
        lead_match = re.match(r"^([^A-Za-z0-9]*)(.*?)([^A-Za-z0-9]*)$", token)
        if lead_match:
            prefix = lead_match.group(1)
            core = lead_match.group(2)
            suffix = lead_match.group(3)
        else:
            prefix, core, suffix = "", token, ""

        if not core or not is_maskable(core):
            result_tokens.append(token)
            continue

        # Derive a per-word seed from card_id, level, and word index
        seed = _word_seed(card_id, level, idx)
        masked_core = mask_word(core, level, seed)
        result_tokens.append(prefix + masked_core + suffix)

    return " ".join(result_tokens)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _word_seed(card_id: str, level: int, word_index: int) -> int:
    """Return a deterministic integer seed for a given (card_id, level, word_index)."""
    key = f"{card_id}:{level}:{word_index}"
    digest = hashlib.md5(key.encode()).digest()
    # Use first 4 bytes as a 32-bit integer
    return int.from_bytes(digest[:4], "big")


def _uniform(seed: int, position: int) -> float:
    """Return a deterministic float in [0, 1) for the given (seed, position) pair."""
    key = f"{seed}:{position}"
    digest = hashlib.md5(key.encode()).digest()
    value = int.from_bytes(digest[:4], "big")
    return value / (2**32)
