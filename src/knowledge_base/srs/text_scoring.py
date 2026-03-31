"""Token-level text comparison for generation card feedback display.

Uses difflib.SequenceMatcher for proper alignment — handles insertions,
deletions, and substitutions mid-sequence without cascading misalignment.
Display only — not used for scheduling.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

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

    Uses _PUNCT_RE for punctuation removal.
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
    """Compare typed tokens against correct tokens using diff alignment.

    Uses SequenceMatcher to find the best alignment between typed and
    correct token sequences, then classifies each position:
    - Aligned and matching exactly → "exact"
    - Aligned and Levenshtein distance == 1 → "close"
    - Aligned but different → "wrong"
    - Present in typed but not correct → "extra"
    - Present in correct but not typed → "missing"

    This handles insertions and deletions mid-sequence without cascading
    misalignment (unlike naive positional comparison).
    """
    results: list[TokenResult] = []
    matcher = SequenceMatcher(None, typed_tokens, correct_tokens)

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                results.append(TokenResult(
                    expected=correct_tokens[j1 + k],
                    typed=typed_tokens[i1 + k],
                    status="exact",
                ))
        elif tag == "replace":
            # Pair up replacements; excess on either side is extra/missing
            typed_slice = typed_tokens[i1:i2]
            correct_slice = correct_tokens[j1:j2]
            pairs = max(len(typed_slice), len(correct_slice))
            for k in range(pairs):
                if k >= len(correct_slice):
                    results.append(TokenResult(
                        expected="", typed=typed_slice[k], status="extra",
                    ))
                elif k >= len(typed_slice):
                    results.append(TokenResult(
                        expected=correct_slice[k], typed="", status="missing",
                    ))
                else:
                    t, e = typed_slice[k], correct_slice[k]
                    if levenshtein(t, e) <= 1:
                        status = "close"
                    else:
                        status = "wrong"
                    results.append(TokenResult(expected=e, typed=t, status=status))
        elif tag == "insert":
            for k in range(j1, j2):
                results.append(TokenResult(
                    expected=correct_tokens[k], typed="", status="missing",
                ))
        elif tag == "delete":
            for k in range(i1, i2):
                results.append(TokenResult(
                    expected="", typed=typed_tokens[k], status="extra",
                ))

    return results
