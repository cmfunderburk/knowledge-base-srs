# German Vocabulary Philosophy Deck Design

## Goal

Build a German-to-English Anki vocabulary deck covering words from Nietzsche's *Also sprach Zarathustra* and Wittgenstein's *Philosophische Untersuchungen* that are **not** already in the existing top-5000 frequency deck (`English-German_Sorted_by_Frequency.apkg`).

Short-term: reading preparation for these two texts. Long-term: expandable foundation for literary/philosophical German vocabulary.

## Corpus

| Text | Tokens | Unique words |
|------|--------|-------------|
| Also sprach Zarathustra (Nietzsche) | ~84,000 | ~9,500 |
| Philosophische Untersuchungen (Wittgenstein) | ~66,000 | ~6,300 |

Source files:
- `resources/texts/Also Sprach Zarathustra.txt` (Project Gutenberg, 19th-century orthography)
- `resources/texts/Philosophische Untersuchungen.md` (Wittgenstein Project, includes Latin passages)

## Exclusion Set

The existing `English-German_Sorted_by_Frequency.apkg` (5,009 cards) covers the top 5,000 German words by frequency. Each entry lists multiple forms (conjugations, declensions). All listed forms are extracted and used as an exclusion set (~9,700 unique forms). Any lemma already represented in this set is excluded from the new deck.

## Pipeline Architecture

```
resources/texts/*.txt,*.md
        |
        v
scripts/german_vocab/build_vocab.py
  1. Tokenize both texts (strip boilerplate, skip Latin passages)
  2. Lemmatize with spaCy (de_core_news_lg)
  3. Load existing .apkg -> exclusion set
  4. Filter: content words, combined frequency >= 4, not in exclusion set
  5. Normalize archaic spellings -> modern lemmas (preserve archaic as metadata)
  6. Fetch Wiktionary definitions, POS, examples
  7. Write data/german_vocab/cards.csv
        |
        v
  [ Manual review: fill gaps, remove unwanted entries ]
        |
        v
scripts/german_vocab/export_apkg.py
  1. Read reviewed cards.csv
  2. Build genanki model with custom fields and two templates
  3. Export to data/german_vocab/german_vocab_philosophy.apkg
```

## Tokenization & Filtering

**Tokenization**: Regex-based (`[a-zA-ZäöüÄÖÜß]+`), applied after:
- Stripping Project Gutenberg boilerplate (Zarathustra)
- Stripping YAML frontmatter (Wittgenstein)
- Skipping Latin passages in Wittgenstein: the Augustine quote in section 1 is bracketed by `cum ipsi...` through `...enuntiabam.` and appears before the German translation in square brackets. spaCy's language detection via POS confidence can flag non-German spans; any token sequence where spaCy assigns mostly `X` (foreign) POS tags is skipped.

**Lemmatization**: spaCy with `de_core_news_lg` model. Produces proper lemmas, POS tags, and handles compounds and irregular forms.

**Archaic normalization**: After spaCy lemmatization, map remaining archaic Nietzsche spellings to modern equivalents (th->t, giebt->gibt, ss->ß where appropriate, ey->ei). If the archaic form differs from the modern lemma, it is preserved in the `archaic_form` field.

**Frequency threshold**: Combined lemma frequency >= 4 across both texts. Expected yield: ~780 cards.

**Exclusion**: Function words (pronouns, articles, prepositions, conjunctions, modal verbs), proper nouns, and any lemma whose base form appears in the existing frequency deck.

## Wiktionary Fetching

**API**: `https://en.wiktionary.org/api/rest_v1/page/definition/{word}`

**Lookup strategy per lemma**:
1. Try the lemma as-is (capitalized for nouns per spaCy POS)
2. On 404, try alternatives: opposite case, infinitive form, singular
3. On hit, extract: POS, first 1-2 English definitions, example sentence + translation if available

**Rate limiting**: 200ms delay between requests.

**Caching**: Wiktionary responses cached to `data/german_vocab/.wiktionary_cache/` as JSON files keyed by word. Re-runs skip cached words.

**Gap handling**: Words with no Wiktionary hit are written to the CSV with empty `english`/`pos` fields and `needs_review` flag set. Expected gap rate: ~3% (~15-25 words).

## CSV Format

File: `data/german_vocab/cards.csv`

Columns:
- `german` — modern lemma (headword)
- `english` — English translation(s) from Wiktionary
- `pos` — part of speech
- `example_de` — German example sentence (from Wiktionary, if available)
- `example_en` — English translation of example (from Wiktionary, if available)
- `archaic_form` — original archaic spelling if different from modern lemma (e.g., "Thorheit" for Torheit)
- `source` — `nietzsche`, `wittgenstein`, or `both`
- `frequency` — combined occurrence count across both texts
- `needs_review` — `x` if Wiktionary lookup failed; empty otherwise

**Overwrite protection**: `build_vocab.py` refuses to overwrite an existing `cards.csv` without `--force`, protecting manual edits.

## Anki Model & Deck Structure

**Model name**: "German Vocab Philosophy"

**Model ID**: Fixed large integer for stable re-exports.

**Fields**:
1. German
2. English
3. POS
4. Example_DE
5. Example_EN
6. Archaic_Form
7. Source
8. Frequency

**Templates**:

- **DE -> EN**: Front shows `German` (+ `Archaic_Form` in parenthetical if present), `POS` in small text. Back shows `English`, example sentences if available.
- **EN -> DE**: Front shows `English`, `POS`. Back shows `German` (+ archaic form), example sentences.

**Deck**: `German Vocabulary::Philosophy`

Each CSV row produces one note with two cards (one per template) in a single deck. After import, use Anki's per-template "Deck Override" (Browse → Cards → Deck) to split DE→EN and EN→DE cards into separate subdecks if desired.

**Stable GUIDs**: SHA-256 hash of the `german` field, truncated. Re-exports update existing cards.

## Dependencies

- `spacy` + `de_core_news_lg` model (lemmatization, POS tagging)
- `genanki` (already installed; .apkg export)
- Standard library: `urllib`, `json`, `csv`, `re`, `sqlite3`, `zipfile`, `hashlib`, `pathlib`

## Output

- `data/german_vocab/cards.csv` — review artifact
- `data/german_vocab/.wiktionary_cache/` — cached API responses
- `data/german_vocab/german_vocab_philosophy.apkg` — final Anki package
