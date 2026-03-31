"""Token-level Levenshtein text comparison for generation card feedback display.

Used to show users which words they got right/wrong when typing LOS statements.
Display only — not used for scheduling.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_PUNCT_RE = re.compile(r"[.,;:!?()\"\'\[\]]+")


def levenshtein(a: str, b: str) -> int:
    """Compute Levenshtein edit distance between two strings.

    Standard dynamic programming implementation.
    Returns the minimum number of single-character edits (insertions,
    deletions, substitutions) required to transform a into b.
    """
    len_a = len(a)
    len_b = len(b)

    # dp[i][j] = edit distance between a[:i] and b[:j]
    dp = list(range(len_b + 1))

    for i in range(1, len_a + 1):
        prev = dp[0]
        dp[0] = i
        for j in range(1, len_b + 1):
            temp = dp[j]
            if a[i - 1] == b[j - 1]:
                dp[j] = prev
            else:
                dp[j] = 1 + min(prev, dp[j], dp[j - 1])
            prev = temp

    return dp[len_b]


def tokenize(text: str) -> list[str]:
    """Split text into lowercase tokens with punctuation stripped.

    Uses re.compile(r"[.,;:!?()\\"'\\[\\]]+") for punctuation removal.
    Empty input returns empty list. Tokens that become empty after
    punctuation stripping are excluded.
    """
    if not text:
        return []
    tokens = []
    for word in text.split():
        cleaned = _PUNCT_RE.sub("", word).lower()
        if cleaned:
            tokens.append(cleaned)
    return tokens


@dataclass
class TokenResult:
    """Result of comparing a single typed token against the expected token.

    Fields:
        expected: the correct token (empty string for 'extra' tokens)
        typed: the token the user typed (empty string for 'missing' tokens)
        status: one of 'exact', 'close', 'wrong', 'missing', 'extra'
    """

    expected: str
    typed: str
    status: str


def compare_tokens(
    typed_tokens: list[str],
    correct_tokens: list[str],
) -> list[TokenResult]:
    """Compare typed tokens against correct tokens sequentially.

    Per-token logic:
    - exact match → "exact"
    - Levenshtein distance == 1 → "close"
    - otherwise → "wrong"
    - extra typed words (beyond length of correct) → "extra"
    - missing correct words (typed shorter than correct) → "missing"

    Returns list[TokenResult] with one entry per token position,
    covering the full length of whichever list is longer.
    """
    results: list[TokenResult] = []
    len_typed = len(typed_tokens)
    len_correct = len(correct_tokens)
    common = min(len_typed, len_correct)

    for i in range(common):
        typed = typed_tokens[i]
        expected = correct_tokens[i]
        if typed == expected:
            status = "exact"
        elif levenshtein(typed, expected) <= 1:
            status = "close"
        else:
            status = "wrong"
        results.append(TokenResult(expected=expected, typed=typed, status=status))

    # Extra typed words beyond the correct sequence
    for i in range(common, len_typed):
        results.append(TokenResult(expected="", typed=typed_tokens[i], status="extra"))

    # Missing correct words not covered by typed sequence
    for i in range(common, len_correct):
        results.append(TokenResult(expected=correct_tokens[i], typed="", status="missing"))

    return results
