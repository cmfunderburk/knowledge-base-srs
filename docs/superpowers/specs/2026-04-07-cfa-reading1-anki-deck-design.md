# CFA Reading 1 Anki Deck — Design Spec

## Overview

Generate a `CFA::Reading 1` Anki deck (.apkg) from a standalone Python script using genanki. The deck covers Learning Module 1 "Rates and Returns" from the 2025 CFA Level I Quantitative Methods curriculum. Cards use two note types: Enhanced Cloze (reveal, not type-in) and Basic (Q&A). All card content is hardcoded in the script.

## Deck Structure

- **Deck name**: `CFA::Reading 1`
- **Deck ID**: stable random large integer (consistent across re-exports)
- **Script location**: `scripts/cfa_reading1/export_apkg.py`
- **Output**: `scripts/cfa_reading1/cfa_reading1.apkg`
- **Run**: `python scripts/cfa_reading1/export_apkg.py`

The `CFA::` prefix creates a parent deck in Anki; future readings (Reading 2, 3, ...) slot in as siblings.

## Note Types

### Enhanced Cloze

- **Model name**: `Enhanced Cloze 2.1 v2` (must match installed addon)
- **Model ID**: stable random large integer (distinct from all other model IDs in the project)
- **Model type**: `genanki.Model.CLOZE`
- **Fields**: Content, Note, Mnemonics, Extra, Cloze99
- **Template**: placeholder `{{cloze:Content}}` / `{{cloze:Content}}<br>{{Note}}` — Anki uses the installed addon's templates on import when the model name matches.
- Only the `Content` field is populated; other fields are empty strings.

### Basic (Q&A)

- **Model name**: `Basic`
- **Model ID**: stable random large integer (distinct from all other model IDs)
- **Model type**: standard (default)
- **Fields**: Front, Back
- **Template**: `{{Front}}` / `{{FrontSide}}<hr id=answer>{{Back}}`

## Card Content

40 notes total: 16 Enhanced Cloze notes (~45 cloze cards) + 24 Basic Q&A notes. All formulas use LaTeX notation rendered by Anki's MathJax support (e.g., `\(R = \frac{P_1 - P_0 + I_1}{P_0}\)`).

Tags per card: section-based, format `CFA::R1::1.x` where x is the section number.

### Section 1.2 — Interest Rates and Time Value of Money

**Cloze notes:**

1. `Interest rate \(r\): {{c1::required rate of return}}, {{c2::discount rate}}, or {{c3::opportunity cost}}.`
   - Tag: `CFA::R1::1.2`

2. `\(r =\) {{c1::real risk-free rate}} + {{c2::inflation premium}} + {{c3::default risk premium}} + {{c4::liquidity premium}} + {{c5::maturity premium}}`
   - Tag: `CFA::R1::1.2`

3. `Nominal risk-free rate \(\approx\) {{c1::real risk-free rate}} + {{c2::inflation premium}}`
   - Tag: `CFA::R1::1.2`

4. `Exact: \((1 + r_{nominal\ RF}) = (1 +\) {{c1::\(r_{real\ RF}\)}})\((1 +\) {{c2::inflation premium}}\()\)`
   - Tag: `CFA::R1::1.2`

**Q&A notes:**

5. Q: `What does the real risk-free rate reflect in economic theory?`
   A: `The time preference of individuals for current versus future real consumption. It is the single-period rate for a completely risk-free security if no inflation were expected.`
   - Tag: `CFA::R1::1.2`

6. Q: `What does the inflation premium compensate for?`
   A: `Expected inflation over the maturity of the debt — the expected loss of purchasing power.`
   - Tag: `CFA::R1::1.2`

7. Q: `What does the default risk premium compensate for?`
   A: `The possibility that the borrower will fail to make a promised payment at the contracted time and in the contracted amount.`
   - Tag: `CFA::R1::1.2`

8. Q: `What does the liquidity premium compensate for?`
   A: `The risk of loss relative to an investment's fair value if it needs to be converted to cash quickly. T-bills bear no liquidity premium; bonds from small, infrequently traded issuers do.`
   - Tag: `CFA::R1::1.2`

9. Q: `What does the maturity premium compensate for?`
   A: `The increased sensitivity of market value to changes in interest rates as maturity extends.`
   - Tag: `CFA::R1::1.2`

### Section 1.3 — Rates of Return

**Cloze notes:**

10. `Total return = {{c1::income yield}} + {{c2::capital gain/loss}}`
    - Tag: `CFA::R1::1.3`

11. `\(R = \frac{ {{c1::P_1}} - {{c2::P_0}} + {{c3::I_1}} }{ {{c4::P_0}} }\)`
    - Tag: `CFA::R1::1.3`

12. `Multi-period HPR: \(R = \prod_{t=1}^{T}(1 + R_t) -\) {{c1::\(1\)}}`
    - Tag: `CFA::R1::1.3`

13. `Harmonic mean: \(\bar{X}_H = \frac{ {{c1::n}} }{ {{c2::\sum_{i=1}^{n}(1/X_i)}} }\)`
    - Tag: `CFA::R1::1.3`

14. `Ordering: {{c1::\(\bar{X}_H\)}} \(\leq\) {{c2::\(\bar{X}_G\)}} \(\leq\) {{c3::\(\bar{X}_A\)}}. Equal only when {{c4::all observations are the same}}.`
    - Tag: `CFA::R1::1.3`

15. `\(\bar{X}_A \times \bar{X}_H =\) {{c1::\((\bar{X}_G)^2\)}}`
    - Tag: `CFA::R1::1.3`

**Q&A notes:**

16. Q: `When should you use the arithmetic mean for return measurement?`
    A: `When estimating the average return over a single period — it is the simple average of one-period returns and has known statistical properties.`
    - Tag: `CFA::R1::1.3`

17. Q: `When should you use the geometric mean for return measurement?`
    A: `When estimating compound growth over multiple periods. It captures how total returns are linked over time and gives the rate you would have to earn each period to match actual cumulative performance.`
    - Tag: `CFA::R1::1.3`

18. Q: `Why is the arithmetic mean biased upward for multi-period returns?`
    A: `It assumes the amount invested at the beginning of each period is the same, ignoring compounding. The bias is particularly severe when returns mix positive and negative values.`
    - Tag: `CFA::R1::1.3`

19. Q: `When is the harmonic mean the appropriate measure, and what is a common finance application?`
    A: `When averaging rates or ratios (amount per unit) applied repeatedly to a fixed quantity yielding a variable number of units. Key application: cost averaging — periodic investment of a fixed dollar amount; the average cost per share equals the harmonic mean of purchase prices.`
    - Tag: `CFA::R1::1.3`

20. Q: `What is the difference between a trimmed mean and a winsorized mean?`
    A: `Trimmed: removes a defined percentage of the largest and smallest values, then averages the rest. Winsorized: replaces extreme values at both ends with the nearest non-extreme observations, then averages. Both reduce the impact of outliers.`
    - Tag: `CFA::R1::1.3`

### Section 1.4 — Money-Weighted and Time-Weighted Return

**Cloze notes:**

21. `Money-weighted return = {{c1::IRR}}: \(\displaystyle\sum_{t=0}^{T} \frac{CF_t}{(1 + IRR)^t} =\) {{c2::\(0\)}}`
    - Tag: `CFA::R1::1.4`

22. `Three steps for time-weighted return: (1) {{c1::price portfolio before each cash flow}}, (2) {{c2::calculate HPR for each subperiod}}, (3) {{c3::link (compound) subperiod returns}}`
    - Tag: `CFA::R1::1.4`

**Q&A notes:**

23. Q: `What does money-weighted return account for?`
    A: `The timing and size of actual cash flows. It reflects the actual return earned on the money invested and is calculated as the IRR of all cash inflows and outflows.`
    - Tag: `CFA::R1::1.4`

24. Q: `Why is time-weighted return preferred for evaluating portfolio managers?`
    A: `It measures compound growth of one unit of currency, insensitive to cash flow timing. Cash additions/withdrawals are outside the manager's control — if a client adds funds at a bad time, MWR is depressed; TWR removes this effect.`
    - Tag: `CFA::R1::1.4`

25. Q: `What is the key limitation of money-weighted return for comparison purposes?`
    A: `Two investors in the same fund with the same portfolio can have different money-weighted returns because they invested different amounts at different times. It does not allow return comparison across individuals or investment opportunities.`
    - Tag: `CFA::R1::1.4`

### Section 1.5 — Annualized Return

**Cloze notes:**

26. `\(R_{annual} = (1 +\) {{c1::\(R_{period}\)}}\()^{c} -\) {{c2::\(1\)}}, where \(c =\) {{c3::number of periods in a year}}`
    - Tag: `CFA::R1::1.5`

27. `For holding periods longer than one year, \(c\) is a {{c1::fraction}} (e.g., 18 months \(\rightarrow c =\) {{c2::\(2/3\)}})`
    - Tag: `CFA::R1::1.5`

28. `\(r_{cc} =\) {{c1::\(\ln(1 + R)\)}} \(=\) {{c2::\(\ln(P_T / P_0)\)}}`
    - Tag: `CFA::R1::1.5`

29. `CC returns are {{c1::additive}}: \(r_{0,T} = r_{0,1} + r_{1,2} + \cdots + r_{T-1,T}\)`
    - Tag: `CFA::R1::1.5`

**Q&A notes:**

30. Q: `Why annualize returns?`
    A: `To enable comparison across investments held for different time periods. All returns are put on a common annual scale.`
    - Tag: `CFA::R1::1.5`

31. Q: `What is the key limitation of annualizing short-term returns?`
    A: `It implicitly assumes returns can be repeated — that the periodic return can be earned every period for a full year. A 5% weekly return annualized to 1,164% is unrealistic.`
    - Tag: `CFA::R1::1.5`

32. Q: `Why are continuously compounded returns used throughout quantitative finance?`
    A: `Because they are additive across time (just sum sub-period CC returns), while holding period returns require multiplying \((1+R)\) terms. This simplifies multi-period calculations.`
    - Tag: `CFA::R1::1.5`

### Section 1.6 — Other Major Return Measures

**Cloze notes:**

33. `After-tax nominal return = total return \(-\) taxes on {{c1::dividends}}, {{c2::interest}}, and {{c3::realized gains}}`
    - Tag: `CFA::R1::1.6`

34. `\((1 + r_{real}) = \frac{(1 +\) {{c1::\(r_{real\ RF}\)}})\((1 +\) {{c2::risk premium}}\()}{1 +\) {{c3::inflation premium}}\(}\)`
    - Tag: `CFA::R1::1.6`

35. `\(R_L = R_P + \frac{ {{c1::V_B}} }{ {{c2::V_E}} }(\) {{c3::\(R_P - r_D\)}} \()\)`
    - Tag: `CFA::R1::1.6`

**Q&A notes:**

36. Q: `What is gross return and how does it treat trading expenses?`
    A: `Return before deduction of management/admin expenses. Trading expenses (commissions) ARE deducted because they are directly related to return generation. Used to compare asset managers' skill.`
    - Tag: `CFA::R1::1.6`

37. Q: `What is net return?`
    A: `Gross return less managerial and administrative expenses. Measures what the investor actually earned.`
    - Tag: `CFA::R1::1.6`

38. Q: `Why are real returns useful for cross-period comparison?`
    A: `Because inflation rates vary over time. Also useful for cross-country comparison when returns are in local currencies with different inflation rates.`
    - Tag: `CFA::R1::1.6`

39. Q: `When does leverage increase vs decrease portfolio returns?`
    A: `Leverage increases returns when \(R_P > r_D\) (portfolio return exceeds borrowing cost). When \(R_P < r_D\), leverage decreases returns. It amplifies both gains and losses.`
    - Tag: `CFA::R1::1.6`

40. Q: `Why is after-tax real return considered the investor's true benchmark, yet rarely calculated by asset managers?`
    A: `It represents the actual compensation for postponing consumption and bearing risk, after all deductions. But managers can't calculate a universal value because the tax component depends on each investor's marginal rate, holding period, and account type.`
    - Tag: `CFA::R1::1.6`

## Implementation Details

### Script pattern

Follows existing `scripts/govt_spending/export_apkg.py` pattern:
- Standalone script with `if __name__ == "__main__"` block
- NOT a pyproject.toml entry point
- Stable GUIDs via SHA-256 hash of card identifier (e.g., `"cfa_r1_cloze_01"`, `"cfa_r1_qa_05"`)
- Stable model IDs and deck ID (random large integers, distinct from existing IDs)

### Models

Two genanki models defined inline:

1. **Enhanced Cloze** — mirrors addon's `Enhanced Cloze 2.1 v2` field structure. Placeholder templates; Anki uses installed addon templates on import.
2. **Basic** — standard Front/Back model with simple Q&A template.

### Data structure

Cards hardcoded as two lists of tuples:

```python
CLOZE_CARDS = [
    ("cfa_r1_cloze_01", "content...", ["CFA::R1::1.2"]),
    ...
]

QA_CARDS = [
    ("cfa_r1_qa_05", "front...", "back...", ["CFA::R1::1.2"]),
    ...
]
```

First element is the card ID used for stable GUID generation.

### Dependencies

- `genanki` (already in pyproject.toml)
- No other dependencies
