# Indicator Guide Anki Deck — Design Spec

## Purpose

Create a standard Anki deck from `docs/indicator-guide.md` for rapid recognition of indicator definitions, scales, and gotchas. This is independent from the knowledge-base SRS's interval scoring system — standard Anki review with Basic and Cloze note types.

## Goals

- **Rapid recognition**: when encountering an indicator in a forecasting question, immediately recall what it measures, its typical scale, and key caveats
- **Atomic cards**: each card tests one specific fact, enabling granular self-grading
- **One-time generation**: a throwaway Python script produces the `.apkg`; ongoing maintenance is manual in Anki

## Card Facets

For each indicator, up to 5 facet types are extracted (not all indicators have all facets):

| Facet | Note type | Front pattern | Back pattern |
|-------|-----------|---------------|--------------|
| **Definition** | Basic | "What does [indicator] measure?" | Core definition from the guide |
| **Unit** | Cloze | "[Indicator] is measured in {{c1::unit}}." | — |
| **Scale tier** | Cloze | "[Indicator] for [tier description]: {{c1::range}}" with example countries on back as context | — |
| **Why it matters** | Basic | "Why is [indicator] useful for forecasting?" | Key reasoning heuristic from the guide |
| **Gotcha/caveat** | Basic | "What's a key limitation/caveat of [indicator]?" | Data limitation, common misinterpretation, or surprising behavior |

### Scale tier cards

Each scale tier is a separate cloze card testing one band (e.g., poorest / middle-income / rich / world average). Example countries appear as context in the cloze sentence but are not themselves tested. Not every indicator has a world average or the same number of tiers — the tiers follow what the guide provides.

### Governance shared scale

The 6 WGI governance indicators share a common -2.5 to +2.5 scale. One set of scale-tier cloze cards covers the shared scale. Per-indicator cards are generated only for definition, why-it-matters, and gotchas.

## Scope

All indicators across all 7 content sections of the guide:

| Section | Indicators | ~Cards |
|---------|-----------|--------|
| Development | 13 | ~70 |
| Technology Adoption | 6 | ~33 |
| Conflict & Security | 7 | ~38 |
| Finance & Markets | 8 | ~40 |
| Education | 4 | ~20 |
| Governance | 6 | ~22 |
| Urban Areas | 6 | ~30 |
| **Total** | **50** | **~250** |

The Descriptive Statistics section is excluded (it's a meta-section describing card types, not a set of indicators).

## Deck Structure

- **Deck name:** `Indicator Guide`
- **No subdecks** — tags handle organization
- **Output file:** `indicator_guide.apkg` in project root

## Note Types

Two genanki models with new unique hardcoded IDs (no conflict with existing interval model `1677887272395` or enhanced cloze `1774552435321`):

1. **Basic** — standard front/back. Used for definition, why-it-matters, and gotcha facets.
2. **Cloze** — standard cloze deletion. Used for unit and scale-tier facets.

Both use Anki's default styling. No custom CSS or JavaScript.

## Tags

Each card gets two tags:

- `section::<section_slug>` — e.g., `section::development`, `section::tech_adoption`, `section::conflict_security`, `section::finance`, `section::education`, `section::governance`, `section::urban_areas`
- `indicator::<indicator_slug>` — e.g., `indicator::gdp_pc_ppp`, `indicator::gini`. Reuses existing slug conventions from `config.py` where possible.

## Script

- **File:** `build_indicator_guide.py` in project root
- **Dependencies:** `genanki` (already in project deps)
- **No config.py dependency** — all card content is inline as Python data structures
- **No markdown parsing** — card content is manually authored in the script
- **Invocation:** `uv run python build_indicator_guide.py`
- **Disposable** — can be deleted after the `.apkg` is generated and imported
