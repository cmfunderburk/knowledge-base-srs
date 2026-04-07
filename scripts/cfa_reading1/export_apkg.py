"""Export CFA Reading 1 flashcards to an Anki .apkg package.

Writes: scripts/cfa_reading1/cfa_reading1.apkg

Two note types:
- Enhanced Cloze 2.1 v2 (cloze deletion, matches installed addon)
- Basic (standard Q&A)
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import genanki

# --- Stable IDs (must not collide with other export scripts) -----------

CLOZE_MODEL_ID = 2026040701
BASIC_MODEL_ID = 2026040702
DECK_ID = 2026040703

OUT_DIR = Path(__file__).parent

# --- Models ------------------------------------------------------------

cloze_model = genanki.Model(
    CLOZE_MODEL_ID,
    "Enhanced Cloze 2.1 v2",
    fields=[
        {"name": "Content"},
        {"name": "Note"},
        {"name": "Mnemonics"},
        {"name": "Extra"},
        {"name": "Cloze99"},
    ],
    templates=[
        {
            "name": "Enhanced Cloze",
            "qfmt": "{{cloze:Content}}",
            "afmt": "{{cloze:Content}}<br>{{Note}}",
        },
    ],
    model_type=genanki.Model.CLOZE,
)

basic_model = genanki.Model(
    BASIC_MODEL_ID,
    "Basic",
    fields=[
        {"name": "Front"},
        {"name": "Back"},
    ],
    templates=[
        {
            "name": "Card 1",
            "qfmt": "{{Front}}",
            "afmt": "{{FrontSide}}<hr id=answer>{{Back}}",
        },
    ],
)


def stable_guid(card_id: str) -> str:
    """Generate a stable GUID from card_id for safe re-import."""
    h = hashlib.sha256(card_id.encode()).hexdigest()
    return h[:10]


# --- Card data ---------------------------------------------------------
# CLOZE_CARDS: list[tuple[str, str, list[str]]] — (card_id, content, tags)
# QA_CARDS:    list[tuple[str, str, str, list[str]]] — (card_id, front, back, tags)

CLOZE_CARDS: list[tuple[str, list[str]]] = [
    # Section 1.2
    (
        "cfa_r1_cloze_01",
        r"Interest rate \(r\): {{c1::required rate of return}}, {{c2::discount rate}}, or {{c3::opportunity cost}}.",
        ["CFA::R1::1.2"],
    ),
    (
        "cfa_r1_cloze_02",
        r"\(r =\) {{c1::real risk-free rate}} + {{c2::inflation premium}} + {{c3::default risk premium}} + {{c4::liquidity premium}} + {{c5::maturity premium}}",
        ["CFA::R1::1.2"],
    ),
    (
        "cfa_r1_cloze_03",
        r"Nominal risk-free rate \(\approx\) {{c1::real risk-free rate}} + {{c2::inflation premium}}",
        ["CFA::R1::1.2"],
    ),
    (
        "cfa_r1_cloze_04",
        r"Exact: \((1 + r_{nominal\ RF}) = (1 +\) {{c1::\(r_{real\ RF}\)}})\((1 +\) {{c2::inflation premium}}\()\)",
        ["CFA::R1::1.2"],
    ),
    # Section 1.3
    (
        "cfa_r1_cloze_10",
        r"Total return = {{c1::income yield}} + {{c2::capital gain/loss}}",
        ["CFA::R1::1.3"],
    ),
    (
        "cfa_r1_cloze_11",
        r"\(R = \frac{ {{c1::P_1}} - {{c2::P_0}} + {{c3::I_1}} }{ {{c4::P_0}} }\)",
        ["CFA::R1::1.3"],
    ),
    (
        "cfa_r1_cloze_12",
        r"Multi-period HPR: \(R = \prod_{t=1}^{T}(1 + R_t) -\) {{c1::\(1\)}}",
        ["CFA::R1::1.3"],
    ),
    (
        "cfa_r1_cloze_13",
        r"Harmonic mean: \(\bar{X}_H = \frac{ {{c1::n}} }{ {{c2::\sum_{i=1}^{n}(1/X_i)}} }\)",
        ["CFA::R1::1.3"],
    ),
    (
        "cfa_r1_cloze_14",
        r"Ordering: {{c1::\(\bar{X}_H\)}} \(\leq\) {{c2::\(\bar{X}_G\)}} \(\leq\) {{c3::\(\bar{X}_A\)}}. Equal only when {{c4::all observations are the same}}.",
        ["CFA::R1::1.3"],
    ),
    (
        "cfa_r1_cloze_15",
        r"\(\bar{X}_A \times \bar{X}_H =\) {{c1::\((\bar{X}_G)^2\)}}",
        ["CFA::R1::1.3"],
    ),
    # Section 1.4
    (
        "cfa_r1_cloze_21",
        r"Money-weighted return = {{c1::IRR}}: \(\displaystyle\sum_{t=0}^{T} \frac{CF_t}{(1 + IRR)^t} =\) {{c2::\(0\)}}",
        ["CFA::R1::1.4"],
    ),
    (
        "cfa_r1_cloze_22",
        "Three steps for time-weighted return: (1) {{c1::price portfolio before each cash flow}}, (2) {{c2::calculate HPR for each subperiod}}, (3) {{c3::link (compound) subperiod returns}}",
        ["CFA::R1::1.4"],
    ),
    # Section 1.5
    (
        "cfa_r1_cloze_26",
        r"\(R_{annual} = (1 +\) {{c1::\(R_{period}\)}}\()^{c} -\) {{c2::\(1\)}}, where \(c =\) {{c3::number of periods in a year}}",
        ["CFA::R1::1.5"],
    ),
    (
        "cfa_r1_cloze_27",
        r"For holding periods longer than one year, \(c\) is a {{c1::fraction}} (e.g., 18 months \(\rightarrow c =\) {{c2::\(2/3\)}})",
        ["CFA::R1::1.5"],
    ),
    (
        "cfa_r1_cloze_28",
        r"\(r_{cc} =\) {{c1::\(\ln(1 + R)\)}} \(=\) {{c2::\(\ln(P_T / P_0)\)}}",
        ["CFA::R1::1.5"],
    ),
    (
        "cfa_r1_cloze_29",
        r"CC returns are {{c1::additive}}: \(r_{0,T} = r_{0,1} + r_{1,2} + \cdots + r_{T-1,T}\)",
        ["CFA::R1::1.5"],
    ),
]

CLOZE_CARDS.extend([
    # Section 1.6
    (
        "cfa_r1_cloze_33",
        r"After-tax nominal return = total return \(-\) taxes on {{c1::dividends}}, {{c2::interest}}, and {{c3::realized gains}}",
        ["CFA::R1::1.6"],
    ),
    (
        "cfa_r1_cloze_34",
        r"\((1 + r_{real}) = \frac{(1 +\) {{c1::\(r_{real\ RF}\)}})\((1 +\) {{c2::risk premium}}\()}{1 +\) {{c3::inflation premium}}\(}\)",
        ["CFA::R1::1.6"],
    ),
    (
        "cfa_r1_cloze_35",
        r"\(R_L = R_P + \frac{ {{c1::V_B}} }{ {{c2::V_E}} }(\) {{c3::\(R_P - r_D\)}} \()\)",
        ["CFA::R1::1.6"],
    ),
])

QA_CARDS: list[tuple[str, str, str, list[str]]] = [
    # Section 1.2
    (
        "cfa_r1_qa_05",
        "What does the real risk-free rate reflect in economic theory?",
        "The time preference of individuals for current versus future real consumption. It is the single-period rate for a completely risk-free security if no inflation were expected.",
        ["CFA::R1::1.2"],
    ),
    (
        "cfa_r1_qa_06",
        "What does the inflation premium compensate for?",
        "Expected inflation over the maturity of the debt — the expected loss of purchasing power.",
        ["CFA::R1::1.2"],
    ),
    (
        "cfa_r1_qa_07",
        "What does the default risk premium compensate for?",
        "The possibility that the borrower will fail to make a promised payment at the contracted time and in the contracted amount.",
        ["CFA::R1::1.2"],
    ),
    (
        "cfa_r1_qa_08",
        "What does the liquidity premium compensate for?",
        "The risk of loss relative to an investment's fair value if it needs to be converted to cash quickly. T-bills bear no liquidity premium; bonds from small, infrequently traded issuers do.",
        ["CFA::R1::1.2"],
    ),
    (
        "cfa_r1_qa_09",
        "What does the maturity premium compensate for?",
        "The increased sensitivity of market value to changes in interest rates as maturity extends.",
        ["CFA::R1::1.2"],
    ),
    # Section 1.3
    (
        "cfa_r1_qa_16",
        "When should you use the arithmetic mean for return measurement?",
        "When estimating the average return over a single period — it is the simple average of one-period returns and has known statistical properties.",
        ["CFA::R1::1.3"],
    ),
    (
        "cfa_r1_qa_17",
        "When should you use the geometric mean for return measurement?",
        "When estimating compound growth over multiple periods. It captures how total returns are linked over time and gives the rate you would have to earn each period to match actual cumulative performance.",
        ["CFA::R1::1.3"],
    ),
    (
        "cfa_r1_qa_18",
        "Why is the arithmetic mean biased upward for multi-period returns?",
        "It assumes the amount invested at the beginning of each period is the same, ignoring compounding. The bias is particularly severe when returns mix positive and negative values.",
        ["CFA::R1::1.3"],
    ),
    (
        "cfa_r1_qa_19",
        "When is the harmonic mean the appropriate measure, and what is a common finance application?",
        "When averaging rates or ratios (amount per unit) applied repeatedly to a fixed quantity yielding a variable number of units. Key application: cost averaging — periodic investment of a fixed dollar amount; the average cost per share equals the harmonic mean of purchase prices.",
        ["CFA::R1::1.3"],
    ),
    (
        "cfa_r1_qa_20",
        "What is the difference between a trimmed mean and a winsorized mean?",
        "Trimmed: removes a defined percentage of the largest and smallest values, then averages the rest. Winsorized: replaces extreme values at both ends with the nearest non-extreme observations, then averages. Both reduce the impact of outliers.",
        ["CFA::R1::1.3"],
    ),
    # Section 1.4
    (
        "cfa_r1_qa_23",
        "What does money-weighted return account for?",
        "The timing and size of actual cash flows. It reflects the actual return earned on the money invested and is calculated as the IRR of all cash inflows and outflows.",
        ["CFA::R1::1.4"],
    ),
    (
        "cfa_r1_qa_24",
        "Why is time-weighted return preferred for evaluating portfolio managers?",
        "It measures compound growth of one unit of currency, insensitive to cash flow timing. Cash additions/withdrawals are outside the manager's control — if a client adds funds at a bad time, MWR is depressed; TWR removes this effect.",
        ["CFA::R1::1.4"],
    ),
    (
        "cfa_r1_qa_25",
        "What is the key limitation of money-weighted return for comparison purposes?",
        "Two investors in the same fund with the same portfolio can have different money-weighted returns because they invested different amounts at different times. It does not allow return comparison across individuals or investment opportunities.",
        ["CFA::R1::1.4"],
    ),
    # Section 1.5
    (
        "cfa_r1_qa_30",
        "Why annualize returns?",
        "To enable comparison across investments held for different time periods. All returns are put on a common annual scale.",
        ["CFA::R1::1.5"],
    ),
    (
        "cfa_r1_qa_31",
        "What is the key limitation of annualizing short-term returns?",
        "It implicitly assumes returns can be repeated — that the periodic return can be earned every period for a full year. A 5% weekly return annualized to 1,164% is unrealistic.",
        ["CFA::R1::1.5"],
    ),
    (
        "cfa_r1_qa_32",
        "Why are continuously compounded returns used throughout quantitative finance?",
        r"Because they are additive across time (just sum sub-period CC returns), while holding period returns require multiplying \((1+R)\) terms. This simplifies multi-period calculations.",
        ["CFA::R1::1.5"],
    ),
    # Section 1.6
    (
        "cfa_r1_qa_36",
        "What is gross return and how does it treat trading expenses?",
        "Return before deduction of management/admin expenses. Trading expenses (commissions) ARE deducted because they are directly related to return generation. Used to compare asset managers' skill.",
        ["CFA::R1::1.6"],
    ),
    (
        "cfa_r1_qa_37",
        "What is net return?",
        "Gross return less managerial and administrative expenses. Measures what the investor actually earned.",
        ["CFA::R1::1.6"],
    ),
    (
        "cfa_r1_qa_38",
        "Why are real returns useful for cross-period comparison?",
        "Because inflation rates vary over time. Also useful for cross-country comparison when returns are in local currencies with different inflation rates.",
        ["CFA::R1::1.6"],
    ),
    (
        "cfa_r1_qa_39",
        r"When does leverage increase vs decrease portfolio returns?",
        r"Leverage increases returns when \(R_P > r_D\) (portfolio return exceeds borrowing cost). When \(R_P < r_D\), leverage decreases returns. It amplifies both gains and losses.",
        ["CFA::R1::1.6"],
    ),
    (
        "cfa_r1_qa_40",
        "Why is after-tax real return considered the investor's true benchmark, yet rarely calculated by asset managers?",
        "It represents the actual compensation for postponing consumption and bearing risk, after all deductions. But managers can't calculate a universal value because the tax component depends on each investor's marginal rate, holding period, and account type.",
        ["CFA::R1::1.6"],
    ),
]
