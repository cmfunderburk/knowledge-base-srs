# Indicator Guide Anki Deck — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate a standard Anki deck (~250 atomic cards) from the indicator guide, using Basic and Cloze note types for rapid recognition of indicator definitions, scales, and caveats.

**Architecture:** Single throwaway Python script (`build_indicator_guide.py`) with all card content hardcoded as Python data structures. Uses genanki to produce `indicator_guide.apkg`. No config.py dependency, no markdown parsing.

**Tech Stack:** Python 3.12+, genanki (already in project deps), uv

---

### Task 1: Script skeleton with models and card generation

**Files:**
- Create: `build_indicator_guide.py` (project root)

- [ ] **Step 1: Create the script with genanki models, deck, and generation loop**

```python
"""One-shot script to generate an Anki deck from the indicator guide.

Run: uv run python build_indicator_guide.py
Output: indicator_guide.apkg
"""

import genanki

# --- Models ---

BASIC_MODEL = genanki.Model(
    1743200001,
    "Indicator Guide Basic",
    fields=[{"name": "Front"}, {"name": "Back"}],
    templates=[
        {
            "name": "Card 1",
            "qfmt": "{{Front}}",
            "afmt": '{{FrontSide}}<hr id="answer">{{Back}}',
        }
    ],
    css=".card { font-family: arial; font-size: 20px; text-align: center; }",
)

CLOZE_MODEL = genanki.Model(
    1743200002,
    "Indicator Guide Cloze",
    fields=[{"name": "Text"}, {"name": "Extra"}],
    templates=[
        {
            "name": "Cloze",
            "qfmt": "{{cloze:Text}}",
            "afmt": "{{cloze:Text}}<br><br>{{Extra}}",
        }
    ],
    model_type=1,
    css=".card { font-family: arial; font-size: 20px; text-align: center; }"
    " .cloze { font-weight: bold; color: blue; }",
)

DECK = genanki.Deck(1743200000, "Indicator Guide")


def add_basic(front: str, back: str, tags: list[str]) -> None:
    DECK.add_note(genanki.Note(model=BASIC_MODEL, fields=[front, back], tags=tags))


def add_cloze(text: str, extra: str, tags: list[str]) -> None:
    DECK.add_note(genanki.Note(model=CLOZE_MODEL, fields=[text, extra], tags=tags))


# --- Card data by section ---
# Each section calls add_basic / add_cloze directly.
# Cards are organized: definition, unit, scale tiers, why-it-matters, gotchas.


def development_cards() -> None:
    """13 indicators: GDP/PPP, poverty, Gini, trade, life expectancy,
    under-5 mortality, maternal mortality, fertility, CO2, renewables,
    energy intensity, population, land area."""
    # Placeholder — filled in Task 2
    pass


def tech_adoption_cards() -> None:
    """6 indicators: internet, mobile, broadband, R&D, hi-tech exports,
    electricity access."""
    pass


def conflict_security_cards() -> None:
    """7 indicators: military (GDP%, USD), armed forces, arms imports,
    homicides, refugees origin, refugees asylum."""
    pass


def finance_cards() -> None:
    """8 indicators: inflation, current account, reserves, real interest rate,
    market cap, stocks traded, domestic credit, remittances."""
    pass


def education_cards() -> None:
    """4 indicators: literacy, secondary enrollment, tertiary enrollment,
    govt education spending."""
    pass


def governance_cards() -> None:
    """6 WGI indicators with shared scale: govt effectiveness, corruption,
    rule of law, regulatory quality, voice/accountability, political stability."""
    pass


def urban_areas_cards() -> None:
    """6 indicators: city population, city CO2, PM2.5, city life expectancy,
    built-up area per capita, city HDI."""
    pass


def main() -> None:
    development_cards()
    tech_adoption_cards()
    conflict_security_cards()
    finance_cards()
    education_cards()
    governance_cards()
    urban_areas_cards()

    genanki.Package(DECK).write_to_file("indicator_guide.apkg")
    print(f"Wrote {len(DECK.notes)} cards to indicator_guide.apkg")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify the script runs (empty deck)**

Run: `uv run python build_indicator_guide.py`
Expected: `Wrote 0 cards to indicator_guide.apkg`

- [ ] **Step 3: Commit skeleton**

```bash
git add build_indicator_guide.py
git commit -m "feat: add indicator guide Anki deck generator skeleton"
```

---

### Task 2: Development section cards (13 indicators, ~86 cards)

**Files:**
- Modify: `build_indicator_guide.py`

- [ ] **Step 1: Replace `development_cards()` with full card content**

```python
def development_cards() -> None:
    S = "section::development"

    # --- GDP per capita (PPP) ---
    t = [S, "indicator::gdp_pc_ppp"]
    add_basic(
        "What does GDP per capita (PPP) measure?",
        "Total economic output per person, adjusted for purchasing power. "
        "PPP adjustment means $1 buys roughly the same basket of goods "
        "everywhere, making cross-country comparisons meaningful.",
        t,
    )
    add_cloze(
        "GDP per capita (PPP) is measured in {{c1::2021 international dollars}}.",
        "",
        t,
    )
    add_cloze(
        "GDP per capita (PPP) for the poorest countries: {{c1::~$2,000}}",
        "e.g., Mozambique, DR Congo",
        t,
    )
    add_cloze(
        "GDP per capita (PPP) for middle-income countries: {{c1::~$15,000}}",
        "e.g., Brazil, Mexico",
        t,
    )
    add_cloze(
        "GDP per capita (PPP) for rich countries: {{c1::~$50,000–80,000}}",
        "e.g., USA, Germany",
        t,
    )
    add_cloze(
        "GDP per capita (PPP), world average: {{c1::~$20,000}}",
        "",
        t,
    )
    add_basic(
        "Why is GDP per capita (PPP) useful for forecasting?",
        "The single most common denominator for country-level development. "
        "Strongly correlated with nearly every other indicator. When uncertain "
        "about another indicator, your GDP per capita prior for that country "
        "is often your best anchor.",
        t,
    )

    # --- Poverty headcount ratio ---
    t = [S, "indicator::poverty_headcount"]
    add_basic(
        "What does the poverty headcount ratio measure?",
        "Share of population living on less than $3.00/day at 2021 purchasing "
        "power parity — the lower-middle-income poverty line.",
        t,
    )
    add_cloze(
        "The poverty headcount ratio measures % of population below "
        "{{c1::$3.00/day (2021 PPP)}}.",
        "",
        t,
    )
    add_cloze(
        "Poverty headcount ratio in rich countries: {{c1::<1%}}",
        "",
        t,
    )
    add_cloze(
        "Poverty headcount ratio in upper-middle-income countries: {{c1::5–15%}}",
        "",
        t,
    )
    add_cloze(
        "Poverty headcount ratio in Sub-Saharan Africa: {{c1::30–60%}}",
        "",
        t,
    )
    add_basic(
        "Why is the poverty headcount ratio useful for forecasting?",
        "Tracks the left tail of income distribution. Falls rapidly during "
        "sustained growth but is stubborn in conflict-affected or landlocked "
        "states. The gap between regions reveals where development gains have "
        "actually landed.",
        t,
    )

    # --- Gini coefficient ---
    t = [S, "indicator::gini"]
    add_basic(
        "What does the Gini coefficient measure?",
        "Summary measure of income inequality, computed from the Lorenz "
        "curve — the cumulative share of income earned by the cumulative "
        "share of population.",
        t,
    )
    add_cloze(
        "The Gini coefficient is measured on a {{c1::0–100}} scale, "
        "where 0 = perfect equality.",
        "",
        t,
    )
    add_cloze(
        "Gini coefficient for Nordic and Eastern European countries: {{c1::25–30}}",
        "",
        t,
    )
    add_cloze(
        "Gini coefficient for most OECD countries: {{c1::35–45}}",
        "",
        t,
    )
    add_cloze(
        "Gini coefficient for Latin America and Sub-Saharan Africa: {{c1::45–55}}",
        "",
        t,
    )
    add_cloze(
        "Gini coefficient for South Africa (near global maximum): {{c1::~63}}",
        "",
        t,
    )
    add_basic(
        "Why is the Gini coefficient useful for forecasting?",
        "Complements GDP per capita — two countries can have identical average "
        "income with very different distributions. Latin America's high Gini "
        "explains why its poverty rates are elevated relative to its GDP. "
        "Changes slowly; big shifts usually signal structural reform or crisis.",
        t,
    )
    add_basic(
        "What's a key data limitation of the Gini coefficient?",
        "No regional aggregates available — only country-level data.",
        t,
    )

    # --- Trade as % of GDP ---
    t = [S, "indicator::trade_pct_gdp"]
    add_basic(
        "What does trade as % of GDP measure?",
        "Total merchandise and services trade (exports + imports) as a share "
        "of GDP. A standard openness metric.",
        t,
    )
    add_cloze(
        "Trade openness is measured as {{c1::% of GDP (exports + imports)}}.",
        "",
        t,
    )
    add_cloze(
        "Trade as % of GDP for large, relatively closed economies: {{c1::25–30%}}",
        "e.g., USA, Brazil, Japan",
        t,
    )
    add_cloze(
        "Trade as % of GDP for mid-size open economies: {{c1::50–80%}}",
        "e.g., Germany, UK",
        t,
    )
    add_cloze(
        "Trade as % of GDP for trade hubs and small open economies: {{c1::>100%}}",
        "e.g., Singapore, Vietnam",
        t,
    )
    add_cloze(
        "Trade as % of GDP, world average: {{c1::~60%}}",
        "",
        t,
    )
    add_basic(
        "Why is trade as % of GDP useful for forecasting?",
        "Predicts exposure to global shocks. High-trade countries are more "
        "affected by supply chain disruptions, commodity price swings, and "
        "trade policy changes. Large countries tend to trade less (as a % of "
        "GDP) simply because more transactions happen domestically.",
        t,
    )

    # --- Life expectancy at birth ---
    t = [S, "indicator::life_expectancy"]
    add_basic(
        "What does life expectancy at birth measure?",
        "Average number of years a newborn would live if current mortality "
        "rates persist. Captures health system quality, nutrition, sanitation, "
        "and violence.",
        t,
    )
    add_cloze(
        "Life expectancy at birth is measured in {{c1::years}}.",
        "",
        t,
    )
    add_cloze(
        "Life expectancy in the poorest Sub-Saharan African countries: "
        "{{c1::50–60 years}}",
        "",
        t,
    )
    add_cloze(
        "Life expectancy in middle-income countries: {{c1::70–75 years}}",
        "",
        t,
    )
    add_cloze(
        "Life expectancy in rich countries: {{c1::78–84 years}}",
        "Japan and South Korea at the top (~84)",
        t,
    )
    add_cloze(
        "Life expectancy, global average: {{c1::~73 years}}",
        "",
        t,
    )
    add_basic(
        "Why is life expectancy useful for forecasting?",
        "One of the strongest summary statistics for overall welfare. "
        "The 1960-to-current trajectory is dramatic — many countries gained "
        "20+ years. Sensitive to HIV/AIDS epidemics (Southern Africa dip in "
        "1990s–2000s), conflict, and famine.",
        t,
    )

    # --- Under-5 mortality rate ---
    t = [S, "indicator::under5_mortality"]
    add_basic(
        "What does the under-5 mortality rate measure?",
        "Probability of dying between birth and age 5, per 1,000 live births. "
        "The most commonly used child survival metric.",
        t,
    )
    add_cloze(
        "Under-5 mortality rate is measured in "
        "{{c1::deaths per 1,000 live births}}.",
        "",
        t,
    )
    add_cloze(
        "Under-5 mortality rate in rich countries: {{c1::3–5}}",
        "",
        t,
    )
    add_cloze(
        "Under-5 mortality rate in middle-income countries: {{c1::20–40}}",
        "",
        t,
    )
    add_cloze(
        "Under-5 mortality rate in the poorest countries: {{c1::50–100+}}",
        "e.g., Nigeria ~100, DR Congo ~80",
        t,
    )
    add_basic(
        "Why is under-5 mortality useful for forecasting?",
        "The decline from 1960 to present is one of the most dramatic "
        "development achievements in history. Falls faster than life expectancy "
        "rises (concentrated at the bottom of the age distribution). Strongly "
        "linked to vaccination coverage, clean water access, and maternal "
        "education.",
        t,
    )

    # --- Maternal mortality ratio ---
    t = [S, "indicator::maternal_mortality"]
    add_basic(
        "What does the maternal mortality ratio measure?",
        "Number of women who die from pregnancy-related causes per 100,000 "
        "live births. Reflects obstetric care quality, emergency care access, "
        "and broader health system capacity.",
        t,
    )
    add_cloze(
        "Maternal mortality ratio is measured in "
        "{{c1::deaths per 100,000 live births}}.",
        "",
        t,
    )
    add_cloze(
        "Maternal mortality ratio in rich countries: {{c1::2–10}}",
        "",
        t,
    )
    add_cloze(
        "Maternal mortality ratio in middle-income countries: {{c1::50–150}}",
        "",
        t,
    )
    add_cloze(
        "Maternal mortality ratio in the poorest countries: {{c1::300–1,000+}}",
        "e.g., Nigeria ~1,000, DR Congo ~500",
        t,
    )
    add_cloze(
        "Maternal mortality ratio, Sub-Saharan Africa average: {{c1::~500}}",
        "",
        t,
    )
    add_basic(
        "Why is maternal mortality useful for forecasting?",
        "Extremely sensitive to health system infrastructure — skilled birth "
        "attendance and emergency obstetric care are the proximate "
        "determinants. One of the widest rich-poor gaps of any health "
        "indicator (100x or more).",
        t,
    )

    # --- Total fertility rate ---
    t = [S, "indicator::fertility_rate"]
    add_basic(
        "What does total fertility rate measure?",
        "Average number of children a woman would have over her lifetime at "
        "current age-specific fertility rates. The replacement rate is ~2.1.",
        t,
    )
    add_cloze(
        "Total fertility rate is measured in {{c1::births per woman}}.",
        "",
        t,
    )
    add_cloze(
        "Total fertility rate in East Asia and Southern Europe: {{c1::1.0–1.5}}",
        "South Korea ~0.9 is the global minimum",
        t,
    )
    add_cloze(
        "Total fertility rate in most rich countries: {{c1::1.5–2.0}}",
        "",
        t,
    )
    add_cloze(
        "Total fertility rate in South/Southeast Asia and Latin America: "
        "{{c1::2.0–4.0}}",
        "",
        t,
    )
    add_cloze(
        "Total fertility rate in Sub-Saharan Africa: {{c1::4.0–6.0+}}",
        "Niger ~7 is the global maximum",
        t,
    )
    add_basic(
        "Why is total fertility rate useful for forecasting?",
        "The central driver of long-run population dynamics. The "
        "1960-to-current trajectory tells the story of the demographic "
        "transition. Below-replacement fertility in much of Asia and Europe "
        "is reshaping dependency ratios, fiscal sustainability, and growth "
        "potential.",
        t,
    )

    # --- CO2 emissions per capita ---
    t = [S, "indicator::co2_pc"]
    add_basic(
        "What does CO2 emissions per capita measure?",
        "Total carbon dioxide equivalent emissions per person, using AR5 "
        "global warming potentials. Includes energy, industrial processes, "
        "and land use.",
        t,
    )
    add_cloze(
        "CO2 emissions per capita is measured in "
        "{{c1::tonnes CO2e per capita}}.",
        "",
        t,
    )
    add_cloze(
        "CO2 emissions per capita in the poorest countries: {{c1::<1 tonne}}",
        "",
        t,
    )
    add_cloze(
        "CO2 emissions per capita in most developing countries: "
        "{{c1::2–5 tonnes}}",
        "",
        t,
    )
    add_cloze(
        "CO2 emissions per capita in Europe and China: {{c1::5–10 tonnes}}",
        "",
        t,
    )
    add_cloze(
        "CO2 emissions per capita in the USA and Australia: "
        "{{c1::15–20 tonnes}}",
        "",
        t,
    )
    add_cloze(
        "CO2 emissions per capita, world average: {{c1::~5 tonnes}}",
        "",
        t,
    )
    add_basic(
        "Why is CO2 emissions per capita useful for forecasting?",
        "The per-capita framing reveals the inequality in climate "
        "responsibility. Useful for estimating national emission totals when "
        "combined with population. Tracks energy mix and industrial structure.",
        t,
    )

    # --- Renewable share of electricity ---
    t = [S, "indicator::renewable_electricity"]
    add_basic(
        "What does renewable share of electricity measure?",
        "Share of electricity generated from renewable sources (hydro, solar, "
        "wind, geothermal, biomass).",
        t,
    )
    add_cloze(
        "Renewable share of electricity is measured as "
        "{{c1::% of total electricity output}}.",
        "",
        t,
    )
    add_cloze(
        "Renewable share of electricity in countries with large hydro "
        "endowments: {{c1::>80%}}",
        "e.g., Brazil, Ethiopia, DR Congo",
        t,
    )
    add_cloze(
        "Renewable share of electricity in many European countries: "
        "{{c1::30–50%}}",
        "",
        t,
    )
    add_cloze(
        "Renewable share for fossil-fuel-dependent economies: {{c1::10–20%}}",
        "",
        t,
    )
    add_cloze(
        "Renewable share of electricity, world average: {{c1::~30%}}",
        "",
        t,
    )
    add_basic(
        "Why is renewable share of electricity useful for forecasting?",
        "High renewable shares often reflect legacy hydropower rather than "
        "recent wind/solar deployment. The rate of change in recent years is "
        "more informative than the level for forecasting climate trajectories.",
        t,
    )
    add_basic(
        "What's a common mistake when interpreting renewable share of "
        "electricity?",
        "Confusing electricity share with total energy share — electricity is "
        "only part of the picture. High shares often reflect legacy "
        "hydropower, not recent wind/solar deployment.",
        t,
    )

    # --- Energy intensity of GDP ---
    t = [S, "indicator::energy_intensity"]
    add_basic(
        "What does energy intensity of GDP measure?",
        "How much primary energy is consumed per unit of economic output. "
        "Lower values mean more energy-efficient economies.",
        t,
    )
    add_cloze(
        "Energy intensity of GDP is measured in "
        "{{c1::MJ per $2021 PPP GDP}}.",
        "",
        t,
    )
    add_cloze(
        "Energy intensity for efficient economies: {{c1::3–4 MJ/$}}",
        "e.g., Japan, UK",
        t,
    )
    add_cloze(
        "Energy intensity, global average: {{c1::5–7 MJ/$}}",
        "",
        t,
    )
    add_cloze(
        "Energy intensity for energy-intensive or cold-climate economies: "
        "{{c1::8–15 MJ/$}}",
        "e.g., Russia, Ukraine",
        t,
    )
    add_basic(
        "Why is energy intensity of GDP useful for forecasting?",
        "Declines over time in most countries as economies shift toward "
        "services and adopt more efficient technologies. Useful for "
        "decomposing emissions growth into GDP growth, energy intensity, and "
        "carbon intensity components.",
        t,
    )

    # --- Population ---
    t = [S, "indicator::population"]
    add_basic(
        "What does the population indicator measure?",
        "Total resident population from census data and projections.",
        t,
    )
    add_cloze(
        "Population is measured in {{c1::millions}}.",
        "",
        t,
    )
    add_cloze(
        "Population of India and China: {{c1::~1,400M each}}",
        "",
        t,
    )
    add_cloze(
        "Population of USA: {{c1::~340M}}",
        "",
        t,
    )
    add_cloze(
        "Population of Indonesia: {{c1::~280M}}",
        "",
        t,
    )
    add_cloze(
        "World total population: {{c1::~8,100M}}",
        "",
        t,
    )
    add_basic(
        "Why is population useful for forecasting?",
        "Denominator for nearly every per-capita indicator. Population "
        "trajectories are highly predictable over 10–20 year horizons (people "
        "already born). The key uncertainties are fertility rates (especially "
        "in Sub-Saharan Africa) and migration.",
        t,
    )

    # --- Land area ---
    t = [S, "indicator::land_area"]
    add_basic(
        "What does the land area indicator measure?",
        "Total land area excluding inland water bodies. Time-invariant "
        "(one value, not era-specific).",
        t,
    )
    add_cloze(
        "Land area is measured in {{c1::km²}}.",
        "",
        t,
    )
    add_cloze(
        "Land area of Russia: {{c1::~17M km²}}",
        "",
        t,
    )
    add_cloze(
        "Land area of China and USA: {{c1::~9M km² each}}",
        "",
        t,
    )
    add_cloze(
        "Land area of India: {{c1::~3.0M km²}}",
        "",
        t,
    )
    add_cloze(
        "Land area of most European countries: {{c1::100,000–600,000 km²}}",
        "",
        t,
    )
    add_basic(
        "Why is land area useful for forecasting?",
        "Context for population density and resource availability. Useful as "
        "a denominator for thinking about agricultural capacity, urbanization "
        "pressure, and territorial scale.",
        t,
    )
```

- [ ] **Step 2: Run the script to verify**

Run: `uv run python build_indicator_guide.py`
Expected: `Wrote 86 cards to indicator_guide.apkg` (approximately)

- [ ] **Step 3: Commit**

```bash
git add build_indicator_guide.py
git commit -m "feat: add development section cards to indicator guide deck"
```

---

### Task 3: Technology Adoption section cards (6 indicators, ~36 cards)

**Files:**
- Modify: `build_indicator_guide.py`

- [ ] **Step 1: Replace `tech_adoption_cards()` with full card content**

```python
def tech_adoption_cards() -> None:
    S = "section::tech_adoption"

    # --- Internet users ---
    t = [S, "indicator::internet_users"]
    add_basic(
        "What does internet users (% of population) measure?",
        "Share of population that has used the internet in the past 3 months.",
        t,
    )
    add_cloze(
        "Internet users is measured as {{c1::% of population}}.",
        "",
        t,
    )
    add_cloze(
        "Internet users in Nordics and Gulf states: {{c1::95%+}}",
        "",
        t,
    )
    add_cloze(
        "Internet users in most rich countries: {{c1::85–95%}}",
        "",
        t,
    )
    add_cloze(
        "Internet users in middle-income countries: {{c1::40–70%}}",
        "",
        t,
    )
    add_cloze(
        "Internet users in the poorest countries: {{c1::10–30%}}",
        "",
        t,
    )
    add_basic(
        "Why is internet users useful for forecasting?",
        "The fastest S-curve adoption in this dataset. Comparing 2000 and "
        "current values reveals how quickly the digital divide narrowed (and "
        "where it persists). A useful proxy for information access, economic "
        "participation, and government service delivery capacity.",
        t,
    )

    # --- Mobile cellular subscriptions ---
    t = [S, "indicator::mobile_subscriptions"]
    add_basic(
        "What does mobile cellular subscriptions measure?",
        "Active SIM card subscriptions per 100 people. Can exceed 100% "
        "because of multi-SIM usage.",
        t,
    )
    add_cloze(
        "Mobile cellular subscriptions is measured as "
        "{{c1::per 100 people}}.",
        "",
        t,
    )
    add_cloze(
        "Mobile subscriptions in many countries: {{c1::>120 per 100}}",
        "People carry multiple SIMs",
        t,
    )
    add_cloze(
        "Mobile subscriptions in most developing countries: "
        "{{c1::80–120 per 100}}",
        "",
        t,
    )
    add_basic(
        "Why is mobile cellular subscriptions useful for forecasting?",
        "The most dramatic technology adoption story for developing countries. "
        "Leapfrogged landlines entirely. Sub-Saharan Africa went from ~0 to "
        "~90 in two decades. Values >100% reflect multi-SIM behavior "
        "(different carriers for calls, data, cross-border).",
        t,
    )
    add_basic(
        "Why can mobile cellular subscriptions exceed 100%?",
        "Multi-SIM usage — people carry different SIMs for calls, data, and "
        "cross-border use.",
        t,
    )

    # --- Fixed broadband subscriptions ---
    t = [S, "indicator::broadband"]
    add_basic(
        "What does fixed broadband subscriptions measure?",
        "Fixed (wired) broadband internet subscriptions per 100 inhabitants. "
        "Does not include mobile broadband.",
        t,
    )
    add_cloze(
        "Fixed broadband subscriptions is measured as "
        "{{c1::per 100 people}}.",
        "",
        t,
    )
    add_cloze(
        "Fixed broadband subscriptions in rich countries: {{c1::30–45}}",
        "e.g., South Korea, France ~45",
        t,
    )
    add_cloze(
        "Fixed broadband subscriptions in middle-income countries: "
        "{{c1::10–25}}",
        "",
        t,
    )
    add_cloze(
        "Fixed broadband subscriptions in the poorest countries: {{c1::<5}}",
        "",
        t,
    )
    add_basic(
        "Why is fixed broadband useful for forecasting?",
        "A better proxy for infrastructure quality than internet usage alone. "
        "High broadband penetration correlates with digital service "
        "sophistication, remote work capacity, and tech sector development. "
        "The gap between mobile and fixed broadband reveals infrastructure "
        "investment patterns.",
        t,
    )

    # --- R&D expenditure ---
    t = [S, "indicator::rnd_expenditure"]
    add_basic(
        "What does R&D expenditure (% of GDP) measure?",
        "Total domestic expenditure on research and development (public + "
        "private sector) as a share of GDP.",
        t,
    )
    add_cloze(
        "R&D expenditure is measured as {{c1::% of GDP}}.",
        "",
        t,
    )
    add_cloze(
        "R&D expenditure for innovation leaders: {{c1::3–5%}}",
        "e.g., Israel ~5%, South Korea ~4.5%",
        t,
    )
    add_cloze(
        "R&D expenditure for most rich countries: {{c1::2–3%}}",
        "",
        t,
    )
    add_cloze(
        "R&D expenditure for middle-income countries: {{c1::1–2%}}",
        "",
        t,
    )
    add_cloze(
        "R&D expenditure, world average: {{c1::~2.5%}}",
        "",
        t,
    )
    add_basic(
        "Why is R&D expenditure useful for forecasting?",
        "One of the few forward-looking indicators — R&D spending today "
        "predicts technological capability 5–10 years out. The gap between "
        "rich and poor countries is large and widening. Data availability is "
        "patchy for developing countries.",
        t,
    )

    # --- High-technology exports ---
    t = [S, "indicator::hitech_exports"]
    add_basic(
        "What does high-technology exports measure?",
        "Exports of products with high R&D intensity (aerospace, computers, "
        "pharmaceuticals, scientific instruments, electrical machinery) as a "
        "share of total manufactured exports.",
        t,
    )
    add_cloze(
        "High-technology exports is measured as "
        "{{c1::% of manufactured exports}}.",
        "",
        t,
    )
    add_cloze(
        "High-tech exports for East Asian tech exporters: {{c1::40–60%}}",
        "e.g., Philippines, South Korea, Malaysia",
        t,
    )
    add_cloze(
        "High-tech exports for most rich countries: {{c1::15–25%}}",
        "",
        t,
    )
    add_basic(
        "Why is high-technology exports useful for forecasting?",
        "Reveals where a country sits in the value chain. High shares can "
        "reflect either domestic innovation (South Korea) or assembly of "
        "imported components (Philippines). The distinction matters for "
        "predicting economic resilience and wage growth.",
        t,
    )

    # --- Electricity access ---
    t = [S, "indicator::electricity_access"]
    add_basic(
        "What does electricity access measure?",
        "Share of population with access to electricity, including both grid "
        "and off-grid solutions.",
        t,
    )
    add_cloze(
        "Electricity access is measured as {{c1::% of population}}.",
        "",
        t,
    )
    add_cloze(
        "Electricity access in most middle-income and all rich countries: "
        "{{c1::100%}}",
        "",
        t,
    )
    add_cloze(
        "Electricity access in the poorest Sub-Saharan African countries: "
        "{{c1::10–50%}}",
        "e.g., DR Congo ~20%, Mozambique ~35%",
        t,
    )
    add_cloze(
        "Electricity access, Sub-Saharan Africa average: {{c1::~50%}}",
        "",
        t,
    )
    add_basic(
        "Why is electricity access useful for forecasting?",
        "A binding constraint on everything else — you can't run schools, "
        "hospitals, internet, or modern industry without it. The last-mile "
        "problem is severe: going from 80% to 100% is disproportionately "
        "expensive. Off-grid solar is changing the picture in rural Africa.",
        t,
    )
```

- [ ] **Step 2: Run the script to verify**

Run: `uv run python build_indicator_guide.py`
Expected: card count increases (~120+ total)

- [ ] **Step 3: Commit**

```bash
git add build_indicator_guide.py
git commit -m "feat: add tech adoption section cards to indicator guide deck"
```

---

### Task 4: Conflict & Security section cards (7 indicators, ~38 cards)

**Files:**
- Modify: `build_indicator_guide.py`

- [ ] **Step 1: Replace `conflict_security_cards()` with full card content**

```python
def conflict_security_cards() -> None:
    S = "section::conflict_security"

    # --- Military expenditure (% of GDP) ---
    t = [S, "indicator::military_pct_gdp"]
    add_basic(
        "What does military expenditure (% of GDP) measure?",
        "Total military spending (personnel, operations, procurement, R&D) "
        "as a share of GDP.",
        t,
    )
    add_cloze(
        "Military expenditure (% of GDP) for most rich democracies: "
        "{{c1::1–2%}}",
        "The NATO 2% target is a useful anchor",
        t,
    )
    add_cloze(
        "Military expenditure (% of GDP) for security-focused states: "
        "{{c1::3–6%}}",
        "e.g., Israel, Saudi Arabia, Russia",
        t,
    )
    add_cloze(
        "USA military expenditure as % of GDP: {{c1::~3.5%}}",
        "",
        t,
    )
    add_basic(
        "Why is military expenditure (% of GDP) useful for forecasting?",
        "Normalizes for country size. Useful for assessing defense burden and "
        "military ambition relative to economic capacity. The NATO 2% "
        "benchmark is a widely-discussed reference point in forecasting "
        "European security questions.",
        t,
    )

    # --- Military expenditure (current US$) ---
    t = [S, "indicator::military_usd"]
    add_basic(
        "What does military expenditure (current US$) measure?",
        "Total military spending in absolute dollar terms (nominal, not "
        "PPP-adjusted).",
        t,
    )
    add_cloze(
        "USA military expenditure: {{c1::~$800B}}",
        "More than the next 10 countries combined",
        t,
    )
    add_cloze(
        "China military expenditure: {{c1::~$290B}}",
        "",
        t,
    )
    add_cloze(
        "India military expenditure: {{c1::~$85B}}",
        "",
        t,
    )
    add_cloze(
        "Russia military expenditure: {{c1::~$70B}}",
        "",
        t,
    )
    add_basic(
        "Why is military expenditure (absolute $) useful for forecasting?",
        "Reveals actual military capability gaps that % of GDP obscures. A "
        "country spending 5% of a $50B GDP still has a tiny military budget. "
        "Nominal dollars also make cumulative spending comparisons across "
        "alliances tractable.",
        t,
    )

    # --- Armed forces personnel ---
    t = [S, "indicator::armed_forces"]
    add_basic(
        "What does armed forces personnel measure?",
        "Active-duty military personnel including paramilitary forces if "
        "organized as a military unit. Measured in thousands.",
        t,
    )
    add_cloze(
        "China armed forces personnel: {{c1::~2,000K}}",
        "",
        t,
    )
    add_cloze(
        "India and USA armed forces personnel: {{c1::~1,400K each}}",
        "",
        t,
    )
    add_cloze(
        "North Korea armed forces personnel: {{c1::~1,300K}}",
        "",
        t,
    )
    add_cloze(
        "Russia armed forces personnel: {{c1::~900K}}",
        "",
        t,
    )
    add_basic(
        "Why is armed forces personnel useful for forecasting?",
        "Personnel size alone says little about capability (technology, "
        "training, doctrine matter more), but it's a useful input for "
        "thinking about mobilization capacity, occupation sustainability, "
        "and demographic burden.",
        t,
    )

    # --- Arms imports ---
    t = [S, "indicator::arms_imports"]
    add_basic(
        "What does arms imports measure?",
        "Transfers of major conventional weapons, valued at constant 1990 "
        "prices using SIPRI trend-indicator values (not market prices). "
        "Measured in millions of constant 1990 US$.",
        t,
    )
    add_cloze(
        "Largest arms importers (India, Saudi Arabia) typically: "
        "{{c1::$2,000–5,000M}}",
        "Constant 1990 US$",
        t,
    )
    add_basic(
        "Why is arms imports useful for forecasting?",
        "Reveals dependency relationships (who buys from whom) and military "
        "modernization patterns. Constant-price valuation makes time "
        "comparisons valid but the numbers don't correspond to actual "
        "procurement costs. Values are lumpy — a single fighter jet deal can "
        "dominate a year.",
        t,
    )

    # --- Intentional homicides ---
    t = [S, "indicator::homicides"]
    add_basic(
        "What does intentional homicides measure?",
        "Unlawful deaths purposefully inflicted by another person, per "
        "100,000 population. Does not include conflict deaths.",
        t,
    )
    add_cloze(
        "Intentional homicides is measured as "
        "{{c1::per 100,000 people}}.",
        "",
        t,
    )
    add_cloze(
        "Homicide rate in East Asia and Western Europe: {{c1::0.5–2}}",
        "",
        t,
    )
    add_cloze(
        "Homicide rate in the USA: {{c1::3–6}}",
        "",
        t,
    )
    add_cloze(
        "Homicide rate in Latin America's worst-affected countries: "
        "{{c1::20–50+}}",
        "e.g., El Salvador, Honduras, Venezuela",
        t,
    )
    add_cloze(
        "Homicide rate, world average: {{c1::~6}}",
        "",
        t,
    )
    add_basic(
        "Why is intentional homicides useful for forecasting?",
        "The single best proxy for everyday personal security. The massive "
        "range (100x between safest and most dangerous countries) is wider "
        "than almost any other social indicator. Latin America's outlier "
        "status relative to its income level is a key stylized fact.",
        t,
    )

    # --- Refugees by country of origin ---
    t = [S, "indicator::refugees_origin"]
    add_basic(
        "What does refugees by country of origin measure?",
        "People forced to cross national borders to escape conflict, "
        "persecution, or disaster, counted by their home country. "
        "Measured in thousands.",
        t,
    )
    add_cloze(
        "Refugees from Syria: {{c1::>6,000K}}",
        "",
        t,
    )
    add_cloze(
        "Refugees from Ukraine (post-2022): {{c1::>6,000K}}",
        "",
        t,
    )
    add_cloze(
        "Refugees from Afghanistan: {{c1::>2,500K}}",
        "",
        t,
    )
    add_basic(
        "Why is refugees by country of origin useful for forecasting?",
        "A direct measure of state failure and conflict severity. The stock "
        "(total refugees) is sticky — people don't return quickly even after "
        "conflicts end. Highly concentrated: a handful of conflicts drive "
        "most of the global total.",
        t,
    )

    # --- Refugees by country of asylum ---
    t = [S, "indicator::refugees_asylum"]
    add_basic(
        "What does refugees by country of asylum measure?",
        "Refugees counted by the country hosting them. "
        "Measured in thousands.",
        t,
    )
    add_cloze(
        "Refugees hosted by Turkey: {{c1::>3,500K}}",
        "",
        t,
    )
    add_cloze(
        "Refugees hosted by Germany: {{c1::~2,000K}}",
        "",
        t,
    )
    add_cloze(
        "Refugees hosted by Pakistan: {{c1::~1,500K}}",
        "",
        t,
    )
    add_basic(
        "Why is refugees by country of asylum useful for forecasting?",
        "Reveals the distribution of hosting burden, which is heavily "
        "concentrated. Neighboring countries bear most of the load. The "
        "ratio of refugees to host-country population is more informative "
        "than the raw number for assessing political and fiscal strain.",
        t,
    )
```

- [ ] **Step 2: Run and verify**

Run: `uv run python build_indicator_guide.py`
Expected: card count increases (~160+ total)

- [ ] **Step 3: Commit**

```bash
git add build_indicator_guide.py
git commit -m "feat: add conflict & security section cards to indicator guide deck"
```

---

### Task 5: Finance & Markets section cards (8 indicators, ~42 cards)

**Files:**
- Modify: `build_indicator_guide.py`

- [ ] **Step 1: Replace `finance_cards()` with full card content**

```python
def finance_cards() -> None:
    S = "section::finance"

    # --- Inflation (CPI) ---
    t = [S, "indicator::inflation"]
    add_basic(
        "What does inflation (CPI) measure?",
        "Year-over-year change in consumer prices for a basket of goods "
        "and services.",
        t,
    )
    add_cloze(
        "Inflation (CPI) is measured as {{c1::annual %}}.",
        "",
        t,
    )
    add_cloze(
        "Inflation for well-anchored central banks: {{c1::1–3%}}",
        "e.g., USA, Eurozone target ~2%",
        t,
    )
    add_cloze(
        "Inflation in many developing countries: {{c1::5–10%}}",
        "",
        t,
    )
    add_cloze(
        "Inflation in crisis episodes: {{c1::20–100%+}}",
        "e.g., Argentina, Turkey, Venezuela",
        t,
    )
    add_basic(
        "Why is inflation useful for forecasting?",
        "Probably the most asked-about macro variable in forecasting. The "
        "distribution is fat-tailed — most countries cluster at 2–8% but "
        "extreme episodes are common. Historical values are especially useful "
        "for calibrating \"how bad could it get\" priors.",
        t,
    )

    # --- Current account balance ---
    t = [S, "indicator::current_account"]
    add_basic(
        "What does current account balance measure?",
        "Net trade in goods, services, and income flows as % of GDP. "
        "Positive = surplus (exporting more than importing). A country's "
        "saving-investment balance with the rest of the world.",
        t,
    )
    add_cloze(
        "Current account balance for oil exporters: {{c1::+5 to +15%}}",
        "e.g., Saudi Arabia, Russia",
        t,
    )
    add_cloze(
        "Current account balance for mercantilist exporters: {{c1::+3 to +8%}}",
        "e.g., Germany, South Korea",
        t,
    )
    add_cloze(
        "Current account balance for most developing countries and USA: "
        "{{c1::-2 to -5%}}",
        "",
        t,
    )
    add_basic(
        "Why is current account balance useful for forecasting?",
        "Persistent deficits signal reliance on foreign capital; persistent "
        "surpluses signal under-consumption. Sudden reversals (\"sudden "
        "stops\") are a classic trigger for financial crises.",
        t,
    )
    add_basic(
        "What's a data limitation of current account balance?",
        "No regional aggregates available.",
        t,
    )

    # --- Total reserves including gold ---
    t = [S, "indicator::reserves"]
    add_basic(
        "What does total reserves including gold measure?",
        "Foreign exchange reserves plus gold holdings at current prices, held "
        "by the central bank. Measured in billions of current US$.",
        t,
    )
    add_cloze(
        "China's total reserves: {{c1::~$3,300B}}",
        "Largest by far",
        t,
    )
    add_cloze(
        "Japan's total reserves: {{c1::~$1,200B}}",
        "",
        t,
    )
    add_basic(
        "Why is total reserves useful for forecasting?",
        "The war chest for defending a currency or absorbing external shocks. "
        "The rule of thumb for adequacy is 3 months of import cover, but the "
        "actual benchmark depends on capital account openness.",
        t,
    )
    add_basic(
        "What's a data limitation of total reserves?",
        "No regional aggregates available. Reserves-to-GDP or "
        "reserves-to-imports ratios are more informative than raw numbers.",
        t,
    )

    # --- Real interest rate ---
    t = [S, "indicator::real_interest_rate"]
    add_basic(
        "What does real interest rate measure?",
        "Nominal lending interest rate minus inflation. The true cost of "
        "borrowing.",
        t,
    )
    add_cloze(
        "Real interest rate in most stable economies during normal times: "
        "{{c1::0–3%}}",
        "",
        t,
    )
    add_basic(
        "Why is real interest rate useful for forecasting?",
        "The price of capital. Negative real rates transfer wealth from "
        "savers to borrowers (including governments with large debts). "
        "Cross-country differences reflect monetary policy credibility, "
        "institutional quality, and risk premia.",
        t,
    )
    add_basic(
        "What's a data limitation of real interest rate?",
        "No regional aggregates available. Historically volatile and can be "
        "negative during high-inflation episodes or financial repression.",
        t,
    )

    # --- Market capitalization (% of GDP) ---
    t = [S, "indicator::market_cap"]
    add_basic(
        "What does market capitalization (% of GDP) measure?",
        "Total value of listed domestic companies on the stock exchange as a "
        "share of GDP.",
        t,
    )
    add_cloze(
        "Market capitalization for financial centers and tech-heavy markets: "
        "{{c1::>100%}}",
        "e.g., USA ~190%, South Korea ~100%",
        t,
    )
    add_cloze(
        "Market capitalization for mid-size markets: {{c1::30–70%}}",
        "",
        t,
    )
    add_basic(
        "Why is market capitalization useful for forecasting?",
        "Proxy for financial depth and the role of equity markets in the "
        "economy. Very high ratios may signal overvaluation. Very low ratios "
        "suggest firms rely on bank lending or informal finance. Volatile "
        "year-to-year (moves with stock prices).",
        t,
    )

    # --- Stocks traded (% of GDP) ---
    t = [S, "indicator::stocks_traded"]
    add_basic(
        "What does stocks traded (% of GDP) measure?",
        "Total value of shares traded on the stock exchange during the year, "
        "as a share of GDP. A liquidity measure.",
        t,
    )
    add_cloze(
        "Stocks traded for the most liquid markets: {{c1::>100%}}",
        "e.g., USA, China",
        t,
    )
    add_cloze(
        "Stocks traded for mid-size markets: {{c1::20–60%}}",
        "",
        t,
    )
    add_basic(
        "Why is stocks traded useful for forecasting?",
        "Complements market capitalization. A market can be large (high cap) "
        "but illiquid (low turnover), which matters for price discovery, risk "
        "management, and capital allocation efficiency.",
        t,
    )

    # --- Domestic credit to private sector ---
    t = [S, "indicator::domestic_credit"]
    add_basic(
        "What does domestic credit to private sector measure?",
        "Financial resources provided to the private sector by banks and "
        "other financial institutions, as a share of GDP. The broadest "
        "measure of bank-intermediated finance.",
        t,
    )
    add_cloze(
        "Domestic credit for deeply banked economies: {{c1::>150%}}",
        "e.g., USA ~200%, Japan ~170%, China ~180%",
        t,
    )
    add_cloze(
        "Domestic credit for most middle-income countries: {{c1::50–100%}}",
        "",
        t,
    )
    add_cloze(
        "Domestic credit in Sub-Saharan Africa average: {{c1::~30%}}",
        "",
        t,
    )
    add_basic(
        "Why is domestic credit to private sector useful for forecasting?",
        "The best single indicator of financial depth. Rapid credit growth "
        "(>10 percentage points/year) is one of the strongest predictors of "
        "future banking crises. Low levels indicate underdeveloped financial "
        "systems where firms rely on retained earnings or informal lending.",
        t,
    )

    # --- Personal remittances received ---
    t = [S, "indicator::remittances"]
    add_basic(
        "What does personal remittances received measure?",
        "Personal transfers and compensation of employees received from "
        "abroad. Money sent home by migrant workers. Measured in billions "
        "of current US$.",
        t,
    )
    add_cloze(
        "India personal remittances received: {{c1::~$115B}}",
        "Largest recipient",
        t,
    )
    add_cloze(
        "Mexico personal remittances received: {{c1::~$60B}}",
        "",
        t,
    )
    add_cloze(
        "Philippines personal remittances received: {{c1::~$40B}}",
        "",
        t,
    )
    add_basic(
        "Why is personal remittances useful for forecasting?",
        "For many developing countries, remittances are a larger and more "
        "stable source of foreign exchange than foreign aid or FDI. "
        "Countercyclical in the origin country (migrants send more when home "
        "country is in crisis), which provides a natural stabilizer.",
        t,
    )
```

- [ ] **Step 2: Run and verify**

Run: `uv run python build_indicator_guide.py`
Expected: card count increases (~200+ total)

- [ ] **Step 3: Commit**

```bash
git add build_indicator_guide.py
git commit -m "feat: add finance & markets section cards to indicator guide deck"
```

---

### Task 6: Education section cards (4 indicators, ~20 cards)

**Files:**
- Modify: `build_indicator_guide.py`

- [ ] **Step 1: Replace `education_cards()` with full card content**

```python
def education_cards() -> None:
    S = "section::education"

    # --- Adult literacy rate ---
    t = [S, "indicator::literacy"]
    add_basic(
        "What does adult literacy rate measure?",
        "Share of the adult population (ages 15+) that can read and write a "
        "short simple statement about their everyday life.",
        t,
    )
    add_cloze(
        "Adult literacy rate is measured as {{c1::% of people ages 15+}}.",
        "",
        t,
    )
    add_cloze(
        "Adult literacy rate in rich countries: {{c1::>99%}}",
        "Effectively universal",
        t,
    )
    add_cloze(
        "Adult literacy rate in most middle-income countries: {{c1::70–95%}}",
        "",
        t,
    )
    add_cloze(
        "Adult literacy rate in some Sub-Saharan African countries: "
        "{{c1::30–60%}}",
        "e.g., Niger ~35%",
        t,
    )
    add_basic(
        "Why is adult literacy rate useful for forecasting?",
        "A floor indicator — it distinguishes very low-development contexts "
        "but provides little differentiation among middle-income and above. "
        "Gender gaps are large in South Asia and West Africa. Data can be "
        "patchy (census-dependent).",
        t,
    )

    # --- Secondary school enrollment ---
    t = [S, "indicator::secondary_enrollment"]
    add_basic(
        "What does secondary school enrollment measure?",
        "Total enrollment in secondary education regardless of age, expressed "
        "as a percentage of the population of official secondary school age. "
        "Gross enrollment ratio — can exceed 100% due to over-age or "
        "repeating students.",
        t,
    )
    add_cloze(
        "Secondary school enrollment in many rich countries: {{c1::>100%}}",
        "Over-age enrollment",
        t,
    )
    add_cloze(
        "Secondary school enrollment in the poorest countries: "
        "{{c1::20–50%}}",
        "Sub-Saharan Africa average ~50%",
        t,
    )
    add_basic(
        "Why is secondary school enrollment useful for forecasting?",
        "The most informative education indicator for middle-income countries. "
        "The gap between primary (near-universal) and secondary enrollment "
        "reveals where the education pipeline leaks. Strongly predicts "
        "workforce quality 10–15 years out.",
        t,
    )

    # --- Tertiary school enrollment ---
    t = [S, "indicator::tertiary_enrollment"]
    add_basic(
        "What does tertiary school enrollment measure?",
        "Gross enrollment ratio for university/college-level education. "
        "Can exceed 100%.",
        t,
    )
    add_cloze(
        "Tertiary enrollment in rich countries with mass higher education: "
        "{{c1::80–100%+}}",
        "e.g., South Korea ~98%, USA ~88%",
        t,
    )
    add_cloze(
        "Tertiary enrollment in middle-income countries: {{c1::30–60%}}",
        "",
        t,
    )
    add_cloze(
        "Tertiary enrollment in low-income countries: {{c1::<10%}}",
        "Sub-Saharan Africa average ~10%",
        t,
    )
    add_basic(
        "Why is tertiary school enrollment useful for forecasting?",
        "The widest education gap between rich and poor countries. High "
        "enrollment doesn't guarantee quality, but predicts the supply of "
        "skilled workers, innovation capacity, and institutional complexity.",
        t,
    )

    # --- Government education expenditure ---
    t = [S, "indicator::education_spending"]
    add_basic(
        "What does government education expenditure measure?",
        "Total government spending on education (all levels) as a share "
        "of GDP.",
        t,
    )
    add_cloze(
        "Government education expenditure for high-spending countries: "
        "{{c1::5–7%}}",
        "e.g., Nordics, some small states",
        t,
    )
    add_cloze(
        "Government education expenditure for most countries: {{c1::3–5%}}",
        "",
        t,
    )
    add_cloze(
        "Government education expenditure, world average: {{c1::~4.5%}}",
        "",
        t,
    )
    add_basic(
        "Why is government education expenditure useful for forecasting?",
        "Spending levels alone don't predict outcomes (efficiency matters "
        "enormously), but persistently low spending is a reliable predictor "
        "of poor outcomes. The variation is narrower than you might expect — "
        "most countries spend 3–6% regardless of income level.",
        t,
    )
```

- [ ] **Step 2: Run and verify**

Run: `uv run python build_indicator_guide.py`
Expected: card count increases (~220+ total)

- [ ] **Step 3: Commit**

```bash
git add build_indicator_guide.py
git commit -m "feat: add education section cards to indicator guide deck"
```

---

### Task 7: Governance section cards (6 indicators + shared scale, ~22 cards)

**Files:**
- Modify: `build_indicator_guide.py`

- [ ] **Step 1: Replace `governance_cards()` with full card content**

```python
def governance_cards() -> None:
    S = "section::governance"

    # --- Shared WGI scale (applies to all 6 governance indicators) ---
    t = [S, "indicator::wgi_shared"]
    add_cloze(
        "All six Worldwide Governance Indicators use a scale from "
        "{{c1::-2.5 (worst) to +2.5 (best)}}.",
        "0 is roughly the global median. Standard deviation ~1.0.",
        t,
    )
    add_cloze(
        "WGI scores for top performers (Nordics, Singapore, New Zealand): "
        "{{c1::+1.5 to +2.5}}",
        "",
        t,
    )
    add_cloze(
        "WGI scores for most OECD countries: {{c1::+0.5 to +1.5}}",
        "",
        t,
    )
    add_cloze(
        "WGI scores for mid-range developing countries: {{c1::-0.5 to +0.5}}",
        "",
        t,
    )
    add_cloze(
        "WGI scores for fragile and conflict-affected states: "
        "{{c1::-1.0 to -2.0}}",
        "",
        t,
    )
    add_basic(
        "What data sources underlie the WGI governance indicators?",
        "Aggregation of dozens of underlying sources: expert surveys, citizen "
        "polls, NGO assessments. No regional aggregates available for any "
        "governance indicator.",
        t,
    )

    # --- Government effectiveness ---
    t = [S, "indicator::govt_effectiveness"]
    add_basic(
        "What does government effectiveness (WGI) measure?",
        "Quality of public services, civil service independence from "
        "political pressure, quality of policy formulation and "
        "implementation, and government credibility.",
        t,
    )
    add_basic(
        "Why is government effectiveness useful for forecasting?",
        "The most \"administrative\" of the six WGI dimensions. Predicts a "
        "government's ability to actually deliver on its stated policies. "
        "Singapore scores very high here despite scoring lower on "
        "voice/accountability — illustrating that the six dimensions "
        "capture different things.",
        t,
    )

    # --- Control of corruption ---
    t = [S, "indicator::corruption"]
    add_basic(
        "What does control of corruption (WGI) measure?",
        "Perceptions of the extent to which public power is exercised for "
        "private gain, including petty corruption, grand corruption, and "
        "state capture.",
        t,
    )
    add_basic(
        "Why is control of corruption useful for forecasting?",
        "One of the strongest predictors of investment climate and aid "
        "effectiveness. Highly persistent — countries rarely move more than "
        "0.3 points per decade. The correlation with GDP per capita is strong "
        "but there are notable outliers (China: high growth despite middling "
        "corruption scores).",
        t,
    )

    # --- Rule of law ---
    t = [S, "indicator::rule_of_law"]
    add_basic(
        "What does rule of law (WGI) measure?",
        "Perceptions of the extent to which agents have confidence in and "
        "abide by the rules of society — contract enforcement, property "
        "rights, police, courts, and the likelihood of crime and violence.",
        t,
    )
    add_basic(
        "Why is rule of law useful for forecasting?",
        "The closest proxy for \"institutional quality\" as used in the "
        "economics literature. Predicts FDI flows, business formation, and "
        "long-run growth better than most policy variables. Captures the gap "
        "between formal laws on the books and actual enforcement.",
        t,
    )

    # --- Regulatory quality ---
    t = [S, "indicator::regulatory_quality"]
    add_basic(
        "What does regulatory quality (WGI) measure?",
        "Perceptions of the government's ability to formulate and implement "
        "sound policies and regulations that permit and promote private "
        "sector development.",
        t,
    )
    add_basic(
        "Why is regulatory quality useful for forecasting?",
        "Captures the business environment — licensing, trade barriers, "
        "price controls, and the overall ease of doing business. "
        "High-regulation countries can score well if the regulations are "
        "well-designed and consistently applied.",
        t,
    )

    # --- Voice and accountability ---
    t = [S, "indicator::voice_accountability"]
    add_basic(
        "What does voice and accountability (WGI) measure?",
        "Perceptions of the extent to which citizens can participate in "
        "selecting their government, as well as freedom of expression, "
        "freedom of association, and free media.",
        t,
    )
    add_basic(
        "Why is voice and accountability useful for forecasting?",
        "The most \"political\" dimension. Correlates with but is distinct "
        "from democracy indices (Freedom House, Polity). Captures the "
        "expressive and participatory dimensions that matter for forecasting "
        "political stability, protest risk, and regime change.",
        t,
    )

    # --- Political stability ---
    t = [S, "indicator::political_stability"]
    add_basic(
        "What does political stability (WGI) measure?",
        "Perceptions of the likelihood of political instability and/or "
        "politically motivated violence, including terrorism.",
        t,
    )
    add_basic(
        "Why is political stability useful for forecasting?",
        "The most volatile of the six governance indicators. Directly "
        "relevant for forecasting conflict risk, coup risk, and civil "
        "unrest. Countries can score well on other governance dimensions "
        "while scoring poorly here (e.g., Turkey: decent regulatory quality "
        "but low political stability).",
        t,
    )
```

- [ ] **Step 2: Run and verify**

Run: `uv run python build_indicator_guide.py`
Expected: card count increases (~240+ total)

- [ ] **Step 3: Commit**

```bash
git add build_indicator_guide.py
git commit -m "feat: add governance section cards to indicator guide deck"
```

---

### Task 8: Urban Areas section cards (6 indicators, ~30 cards)

**Files:**
- Modify: `build_indicator_guide.py`

- [ ] **Step 1: Replace `urban_areas_cards()` with full card content**

```python
def urban_areas_cards() -> None:
    S = "section::urban_areas"

    # --- Population (city) ---
    t = [S, "indicator::city_population"]
    add_basic(
        "What does city population (GHS-UCDB) measure?",
        "Total population within the urban centre boundary as defined by the "
        "GHSL built-up area methodology. Not the same as administrative city "
        "boundaries (usually larger).",
        t,
    )
    add_cloze(
        "Guangzhou population (GHSL definition, captures Pearl River Delta): "
        "{{c1::~65M}}",
        "",
        t,
    )
    add_cloze(
        "Tokyo population (GHSL definition): {{c1::~37M}}",
        "",
        t,
    )
    add_cloze(
        "Jakarta population (GHSL definition): {{c1::~35M}}",
        "",
        t,
    )
    add_basic(
        "Why is the GHSL city population definition important for "
        "forecasting?",
        "City populations are notoriously definition-dependent. The GHSL "
        "satellite-derived boundaries provide consistent cross-city "
        "comparisons but can differ dramatically from official figures. "
        "Understanding which definition is being used is critical.",
        t,
    )

    # --- CO2 emissions per capita (city) ---
    t = [S, "indicator::city_co2"]
    add_basic(
        "What does city-level CO2 emissions per capita measure?",
        "Urban-area CO2 emissions per person, estimated from downscaled "
        "national emissions data combined with spatial proxies. Measured in "
        "tonnes per person.",
        t,
    )
    add_cloze(
        "City CO2 per capita for South Asian cities: {{c1::1–3 tonnes}}",
        "",
        t,
    )
    add_cloze(
        "City CO2 per capita for East Asian and Latin American cities: "
        "{{c1::3–8 tonnes}}",
        "",
        t,
    )
    add_cloze(
        "City CO2 per capita for high-income country cities: "
        "{{c1::10–20+ tonnes}}",
        "e.g., Los Angeles ~15",
        t,
    )
    add_basic(
        "Why is city-level CO2 useful for forecasting?",
        "Urbanization is both a driver of emissions (transport, construction) "
        "and a mitigator (density, shared infrastructure). Comparing "
        "city-level to national per-capita emissions reveals whether "
        "urbanization is net-positive or net-negative for climate.",
        t,
    )

    # --- PM2.5 concentration ---
    t = [S, "indicator::pm25"]
    add_basic(
        "What does PM2.5 concentration measure?",
        "Annual mean concentration of fine particulate matter (particles "
        "<2.5 micrometers) in micrograms per cubic meter. The most "
        "health-relevant air quality metric.",
        t,
    )
    add_cloze(
        "WHO PM2.5 guideline: {{c1::5 ug/m3}}",
        "Almost no city meets this",
        t,
    )
    add_cloze(
        "PM2.5 in clean cities (Tokyo, London): {{c1::10–15 ug/m3}}",
        "",
        t,
    )
    add_cloze(
        "PM2.5 in moderately polluted cities (Mexico City, Bangkok): "
        "{{c1::30–60 ug/m3}}",
        "",
        t,
    )
    add_cloze(
        "PM2.5 in severely polluted cities (Delhi, Dhaka, Lahore): "
        "{{c1::80–120+ ug/m3}}",
        "",
        t,
    )
    add_basic(
        "Why is PM2.5 useful for forecasting?",
        "The air pollution metric with the strongest health evidence. "
        "Responsible for millions of premature deaths annually. The "
        "2000-to-2020 trajectory is mixed — improving in some cities "
        "(Beijing), worsening in others (African cities).",
        t,
    )

    # --- Life expectancy (city) ---
    t = [S, "indicator::city_life_expectancy"]
    add_basic(
        "What does city-level life expectancy measure?",
        "City-level life expectancy, estimated from subnational health data "
        "and demographic models.",
        t,
    )
    add_cloze(
        "Life expectancy for cities in rich countries: {{c1::80–85 years}}",
        "",
        t,
    )
    add_cloze(
        "Life expectancy for middle-income-country cities: "
        "{{c1::70–78 years}}",
        "",
        t,
    )
    add_cloze(
        "Life expectancy for cities in the poorest countries: "
        "{{c1::55–65 years}}",
        "e.g., Kinshasa ~60, Lagos ~55",
        t,
    )
    add_basic(
        "Why is city-level life expectancy useful for forecasting?",
        "The urban advantage in health is real but not universal — some very "
        "large developing-country cities have life expectancy below their "
        "national average due to slum conditions, pollution, and "
        "overcrowding.",
        t,
    )

    # --- Built-up area per capita ---
    t = [S, "indicator::built_up_per_capita"]
    add_basic(
        "What does built-up area per capita measure?",
        "Total built-up area (buildings, roads, paved surfaces) divided by "
        "population. A satellite-derived density proxy. Measured in m2 per "
        "person.",
        t,
    )
    add_cloze(
        "Built-up area per capita for very dense cities: "
        "{{c1::20–40 m2}}",
        "e.g., Dhaka ~15, Mumbai ~20",
        t,
    )
    add_cloze(
        "Built-up area per capita for mid-density cities: "
        "{{c1::50–100 m2}}",
        "e.g., Beijing, Mexico City",
        t,
    )
    add_cloze(
        "Built-up area per capita for sprawling cities: "
        "{{c1::150–300+ m2}}",
        "e.g., Los Angeles ~200",
        t,
    )
    add_basic(
        "Why is built-up area per capita useful for forecasting?",
        "The physical footprint of urbanization. Declining per-capita "
        "built-up area means densification (common in fast-growing "
        "developing-country cities). Rising values mean sprawl. Has "
        "implications for transport energy use, infrastructure costs, "
        "and livability.",
        t,
    )

    # --- Human Development Index (city) ---
    t = [S, "indicator::city_hdi"]
    add_basic(
        "What does city-level HDI measure?",
        "Composite index of life expectancy, education, and income, adapted "
        "to the city level from subnational data. Scale from 0 to 1.",
        t,
    )
    add_cloze(
        "City HDI for cities in rich countries: {{c1::0.90–0.95}}",
        "e.g., Tokyo, London, Paris",
        t,
    )
    add_cloze(
        "City HDI for middle-income-country cities: {{c1::0.70–0.85}}",
        "",
        t,
    )
    add_cloze(
        "City HDI for cities in the poorest countries: {{c1::0.40–0.60}}",
        "e.g., Kinshasa ~0.47",
        t,
    )
    add_basic(
        "Why is city-level HDI useful for forecasting?",
        "Summarizes multidimensional welfare in a single number. The "
        "within-country city-vs-national gap reveals urban advantage. Useful "
        "as a composite anchor when you're unsure about individual "
        "sub-indicators for a city.",
        t,
    )
```

- [ ] **Step 2: Run and verify**

Run: `uv run python build_indicator_guide.py`
Expected: ~250+ cards total

- [ ] **Step 3: Commit**

```bash
git add build_indicator_guide.py
git commit -m "feat: add urban areas section cards to indicator guide deck"
```

---

### Task 9: Final generation and verification

**Files:**
- None modified — verification only

- [ ] **Step 1: Run the script and verify output**

Run: `uv run python build_indicator_guide.py`
Expected: `Wrote ~250 cards to indicator_guide.apkg`

- [ ] **Step 2: Verify the .apkg file exists and has reasonable size**

Run: `ls -la indicator_guide.apkg`
Expected: file exists, size > 10KB

- [ ] **Step 3: Print a summary of cards per section**

Add a temporary count print at the end of `main()` to verify distribution, or count the `add_basic` and `add_cloze` calls manually. Verify roughly:
- Development: ~86
- Tech Adoption: ~36
- Conflict & Security: ~38
- Finance: ~42
- Education: ~20
- Governance: ~22
- Urban Areas: ~30

- [ ] **Step 4: Final commit**

```bash
git add build_indicator_guide.py indicator_guide.apkg
git commit -m "feat: complete indicator guide Anki deck (250 cards)"
```

After import into Anki, `build_indicator_guide.py` can be deleted if desired.
