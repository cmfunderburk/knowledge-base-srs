# Indicator Guide

A reference for all indicators in the calibration training system. Each entry explains what the indicator measures, why it matters for forecasting, and how to think about its scale.

The system covers 47 countries (7 regions, 15 major economies, 25 long-tail), 50 cities, and 8 decks. Cards ask you to estimate values as 95% confidence intervals or point predictions.

---

## Development

Core economic and demographic indicators. Most are available across three eras (1960, 1990, current), making them useful for building intuition about long-run development trajectories.

### GDP per capita (PPP)

- **Unit:** 2021 international dollars
- **Source:** World Bank (`NY.GDP.PCAP.PP.KD`)
- **What it measures:** Total economic output per person, adjusted for purchasing power. PPP adjustment means $1 buys roughly the same basket of goods everywhere, making cross-country comparisons meaningful.
- **Scale intuition:** ~$2,000 for the poorest countries (Mozambique, DR Congo). ~$15,000 for middle-income (Brazil, Mexico). ~$50,000--80,000 for rich countries (USA, Germany). World average ~$20,000.
- **Why it matters:** The single most common denominator for country-level development. Strongly correlated with nearly every other indicator in this system. When uncertain about another indicator, your GDP per capita prior for that country is often your best anchor.

### Poverty headcount ratio

- **Unit:** % of population below $3.00/day (2021 PPP)
- **Source:** World Bank (`SI.POV.DDAY`)
- **What it measures:** Share of population living on less than $3.00/day at 2021 purchasing power parity. This is the lower-middle-income poverty line -- more relevant for developing countries than the extreme poverty line ($2.15).
- **Scale intuition:** <1% in rich countries. 5--15% in upper-middle-income countries. 30--60% in Sub-Saharan Africa. Historically, >60% was common across much of Asia and Africa before 1990.
- **Why it matters:** Tracks the left tail of income distribution. Falls rapidly during sustained growth but is stubborn in conflict-affected or landlocked states. The gap between regions tells you a lot about where development gains have actually landed.

### Gini coefficient

- **Unit:** 0--100 scale (0 = perfect equality)
- **Source:** World Bank (`SI.POV.GINI`)
- **What it measures:** Summary measure of income inequality. Computed from the Lorenz curve -- the cumulative share of income earned by the cumulative share of population.
- **Scale intuition:** 25--30 for Nordics and some Eastern European countries. 35--45 for most OECD. 45--55 for Latin America and Sub-Saharan Africa. South Africa at ~63 is near the global maximum.
- **Why it matters:** Complements GDP per capita -- two countries can have identical average income with very different distributions. Latin America's high Gini explains why its poverty rates are elevated relative to its GDP. Changes slowly; big shifts usually signal structural reform or crisis.
- **Note:** No regional aggregates available -- only country-level data.

### Trade as % of GDP

- **Unit:** % of GDP (exports + imports)
- **Source:** World Bank (`NE.TRD.GNFS.ZS`)
- **What it measures:** Total merchandise and services trade (exports + imports) as a share of GDP. A standard openness metric.
- **Scale intuition:** 25--30% for large, relatively closed economies (USA, Brazil, Japan). 50--80% for mid-size open economies (Germany, UK). >100% for trade hubs and small open economies (Singapore, Vietnam). World average ~60%.
- **Why it matters:** Predicts exposure to global shocks. High-trade countries are more affected by supply chain disruptions, commodity price swings, and trade policy changes. Large countries tend to trade less (as a % of GDP) simply because more transactions happen domestically.

### Life expectancy at birth

- **Unit:** years
- **Source:** World Bank (`SP.DYN.LE00.IN`)
- **What it measures:** Average number of years a newborn would live if current mortality rates persist. Captures health system quality, nutrition, sanitation, and violence.
- **Scale intuition:** 50--60 years in the poorest Sub-Saharan African countries. 70--75 in middle-income countries. 78--84 in rich countries. Japan and South Korea at the top (~84). Global average ~73.
- **Why it matters:** One of the strongest summary statistics for overall welfare. The 1960-to-current trajectory is dramatic -- many countries gained 20+ years. Sensitive to HIV/AIDS epidemics (Southern Africa dip in the 1990s--2000s), conflict, and famine.

### Under-5 mortality rate

- **Unit:** deaths per 1,000 live births
- **Source:** World Bank (`SH.DYN.MORT`)
- **What it measures:** Probability of dying between birth and age 5, per 1,000 live births. The most commonly used child survival metric.
- **Scale intuition:** 3--5 in rich countries. 20--40 in middle-income countries. 50--100+ in the poorest countries (Nigeria ~100, DR Congo ~80). Historical rates in 1960 were 200+ in many African countries.
- **Why it matters:** The decline from 1960 to present is one of the most dramatic development achievements in history. Falls faster than life expectancy rises (concentrated at the bottom of the age distribution). Strongly linked to vaccination coverage, clean water access, and maternal education.

### Maternal mortality ratio

- **Unit:** deaths per 100,000 live births
- **Source:** World Bank (`SH.STA.MMRT`)
- **What it measures:** Number of women who die from pregnancy-related causes per 100,000 live births. Reflects obstetric care quality, emergency care access, and broader health system capacity.
- **Scale intuition:** 2--10 in rich countries. 50--150 in middle-income countries. 300--1,000+ in the poorest countries (Nigeria ~1,000, DR Congo ~500). Sub-Saharan Africa averages ~500.
- **Why it matters:** Extremely sensitive to health system infrastructure -- skilled birth attendance and emergency obstetric care are the proximate determinants. One of the widest rich-poor gaps of any health indicator (100x or more).

### Total fertility rate

- **Unit:** births per woman
- **Source:** World Bank (`SP.DYN.TFRT.IN`)
- **What it measures:** Average number of children a woman would have over her lifetime at current age-specific fertility rates. The replacement rate is ~2.1.
- **Scale intuition:** 1.0--1.5 in East Asia and Southern Europe (South Korea ~0.9 is the global minimum). 1.5--2.0 in most rich countries. 2.0--4.0 in South/Southeast Asia and Latin America. 4.0--6.0+ in Sub-Saharan Africa (Niger ~7 is the global maximum).
- **Why it matters:** The central driver of long-run population dynamics. The 1960-to-current trajectory tells the story of the demographic transition. Below-replacement fertility in much of Asia and Europe is reshaping dependency ratios, fiscal sustainability, and growth potential.

### CO2 emissions per capita

- **Unit:** tonnes CO2e per capita
- **Source:** World Bank (`EN.GHG.CO2.PC.CE.AR5`)
- **What it measures:** Total carbon dioxide equivalent emissions per person, using AR5 global warming potentials. Includes energy, industrial processes, and land use.
- **Scale intuition:** <1 tonne in the poorest countries. 2--5 in most developing countries. 5--10 in Europe and China. 15--20 in the USA and Australia. Saudi Arabia and some Gulf states >20. World average ~5.
- **Why it matters:** The per-capita framing reveals the inequality in climate responsibility. Useful for estimating national emission totals when combined with population. Tracks energy mix and industrial structure.

### Renewable share of electricity

- **Unit:** % of total electricity output
- **Source:** World Bank (`EG.ELC.RNEW.ZS`)
- **What it measures:** Share of electricity generated from renewable sources (hydro, solar, wind, geothermal, biomass).
- **Scale intuition:** >80% in countries with large hydro endowments (Brazil, Ethiopia, DR Congo). 30--50% in many European countries. 10--20% for fossil-fuel-dependent economies. ~0% for oil states (Saudi Arabia). World average ~30%.
- **Why it matters:** Don't confuse with total energy -- electricity is only part of the picture. High renewable shares often reflect hydropower rather than wind/solar. The rate of change in recent years (solar/wind deployment) is more informative than the level for forecasting climate trajectories.

### Energy intensity of GDP

- **Unit:** MJ per $2021 PPP GDP
- **Source:** World Bank (`EG.EGY.PRIM.PP.KD`)
- **What it measures:** How much primary energy is consumed per unit of economic output. Lower values mean more energy-efficient economies.
- **Scale intuition:** 3--4 MJ/$ for efficient economies (Japan, UK). 5--7 MJ/$ for the global average. 8--15 MJ/$ for energy-intensive or cold-climate economies (Russia, Ukraine). Oil-exporting states can be very high due to subsidized domestic energy consumption.
- **Why it matters:** Declines over time in most countries as economies shift toward services and adopt more efficient technologies. Useful for decomposing emissions growth into GDP growth, energy intensity, and carbon intensity components.

### Population

- **Unit:** millions
- **Source:** World Bank (`SP.POP.TOTL`)
- **What it measures:** Total resident population from census data and projections.
- **Scale intuition:** India and China ~1,400M each. USA ~340M. Indonesia ~280M. Many African countries have doubled or tripled since 1990. World total ~8,100M.
- **Why it matters:** Denominator for nearly every per-capita indicator. Population trajectories are highly predictable over 10--20 year horizons (people already born). The key uncertainties are fertility rates (especially in Sub-Saharan Africa) and migration.

### Land area

- **Unit:** km²
- **Source:** World Bank (`AG.LND.TOTL.K2`)
- **What it measures:** Total land area excluding inland water bodies. Time-invariant (one value, not era-specific).
- **Scale intuition:** Russia ~17M km². China ~9.4M. USA ~9.1M. India ~3.0M. Most European countries 100,000--600,000. Small states <30,000.
- **Why it matters:** Context for population density and resource availability. Useful as a denominator for thinking about agricultural capacity, urbanization pressure, and territorial scale.

---

## Technology Adoption

Tracks the diffusion of connectivity, innovation capacity, and infrastructure access. Four eras (1990, 2000, 2010, current) capture the S-curve adoption pattern of digital technologies.

### Internet users

- **Unit:** % of population
- **Source:** World Bank (`IT.NET.USER.ZS`)
- **What it measures:** Share of population that has used the internet in the past 3 months.
- **Scale intuition:** 95%+ in Nordics and Gulf states. 85--95% in most rich countries. 40--70% in middle-income countries. 10--30% in the poorest countries. The 2000 values are dramatic -- even rich countries were at 30--50%.
- **Why it matters:** The fastest S-curve adoption in this dataset. Comparing 2000 and current values reveals how quickly the digital divide narrowed (and where it persists). A useful proxy for information access, economic participation, and government service delivery capacity.

### Mobile cellular subscriptions

- **Unit:** per 100 people
- **Source:** World Bank (`IT.CEL.SETS.P2`)
- **What it measures:** Active SIM card subscriptions per 100 people. Can exceed 100% because of multi-SIM usage.
- **Scale intuition:** >120 per 100 in many countries (people carry multiple SIMs). 80--120 in most developing countries. Was <5 everywhere in 1990. Sub-Saharan Africa went from ~0 to ~90 in two decades.
- **Why it matters:** The most dramatic technology adoption story for developing countries. Leapfrogged landlines entirely. The >100% values are confusing at first but reflect genuine multi-SIM behavior (different carriers for calls, data, cross-border).

### Fixed broadband subscriptions

- **Unit:** per 100 people
- **Source:** World Bank (`IT.NET.BBND.P2`)
- **What it measures:** Fixed (wired) broadband internet subscriptions per 100 inhabitants. Does not include mobile broadband.
- **Scale intuition:** 30--45 in rich countries (South Korea, France ~45). 10--25 in middle-income countries. <5 in the poorest countries. Much lower than mobile subscriptions everywhere.
- **Why it matters:** A better proxy for infrastructure quality than internet usage alone. High broadband penetration correlates with digital service sophistication, remote work capacity, and tech sector development. The gap between mobile and fixed broadband penetration reveals infrastructure investment patterns.

### R&D expenditure

- **Unit:** % of GDP
- **Source:** World Bank (`GB.XPD.RSDV.GD.ZS`)
- **What it measures:** Total domestic expenditure on research and development (public + private sector) as a share of GDP.
- **Scale intuition:** 3--5% for innovation leaders (Israel ~5%, South Korea ~4.5%). 2--3% for most rich countries. 1--2% for middle-income countries. <0.5% for the poorest countries. World average ~2.5%.
- **Why it matters:** One of the few forward-looking indicators -- R&D spending today predicts technological capability 5--10 years out. The gap between rich and poor countries is large and widening. Data availability is patchy for developing countries.

### High-technology exports

- **Unit:** % of manufactured exports
- **Source:** World Bank (`TX.VAL.TECH.MF.ZS`)
- **What it measures:** Exports of products with high R&D intensity (aerospace, computers, pharmaceuticals, scientific instruments, electrical machinery) as a share of total manufactured exports.
- **Scale intuition:** 40--60% for East Asian tech exporters (Philippines, South Korea, Malaysia). 15--25% for most rich countries. <10% for commodity exporters and many developing countries.
- **Why it matters:** Reveals where a country sits in the value chain. High shares can reflect either domestic innovation (South Korea) or assembly of imported components (Philippines). The distinction matters for predicting economic resilience and wage growth.

### Electricity access

- **Unit:** % of population
- **Source:** World Bank (`EG.ELC.ACCS.ZS`)
- **What it measures:** Share of population with access to electricity, including both grid and off-grid solutions.
- **Scale intuition:** 100% in most middle-income and all rich countries. 50--90% in lower-middle-income countries. 10--50% in the poorest Sub-Saharan African countries (DR Congo ~20%, Mozambique ~35%). Sub-Saharan Africa average ~50%.
- **Why it matters:** A binding constraint on everything else -- you can't run schools, hospitals, internet, or modern industry without it. The last-mile problem is severe: going from 80% to 100% is disproportionately expensive. Off-grid solar is changing the picture in rural Africa.

---

## Conflict & Security

Military capacity, arms flows, and security outcomes. Eras are 1960, 1990, and current.

### Military expenditure (% of GDP)

- **Unit:** % of GDP
- **Source:** World Bank (`MS.MIL.XPND.GD.ZS`)
- **What it measures:** Total military spending (personnel, operations, procurement, R&D) as a share of GDP.
- **Scale intuition:** 1--2% for most rich democracies (the NATO 2% target is a useful anchor). 3--6% for security-focused states (Israel, Saudi Arabia, Russia). <1% for many developing countries. USA ~3.5%.
- **Why it matters:** The % of GDP framing normalizes for country size. Useful for assessing defense burden and military ambition relative to economic capacity. The NATO 2% benchmark is a widely-discussed reference point in forecasting European security questions.

### Military expenditure (current US$)

- **Unit:** billions of current US$
- **Source:** World Bank (`MS.MIL.XPND.CD`)
- **What it measures:** Same spending in absolute dollar terms (nominal, not PPP-adjusted).
- **Scale intuition:** USA ~800B (more than the next 10 countries combined). China ~290B. India ~85B. Russia ~70B. Most European countries $30--70B. Many developing countries <$5B.
- **Why it matters:** The absolute numbers reveal actual military capability gaps that % of GDP obscures. A country spending 5% of a $50B GDP still has a tiny military budget. Nominal dollars also make cumulative spending comparisons across alliances tractable.

### Armed forces personnel

- **Unit:** thousands
- **Source:** World Bank (`MS.MIL.TOTL.P1`)
- **What it measures:** Active-duty military personnel including paramilitary forces if organized as a military unit.
- **Scale intuition:** China ~2,000K. India ~1,400K. USA ~1,400K. Russia ~900K. North Korea ~1,300K. Most European countries 100--300K. Many small/developing countries <50K.
- **Why it matters:** Personnel size alone says little about capability (technology, training, doctrine matter more), but it's a useful input for thinking about mobilization capacity, occupation sustainability, and demographic burden.

### Arms imports

- **Unit:** millions (constant 1990 US$)
- **Source:** World Bank (`MS.MIL.MPRT.KD`)
- **What it measures:** Transfers of major conventional weapons, valued at constant 1990 prices using SIPRI trend-indicator values (not market prices).
- **Scale intuition:** India and Saudi Arabia typically $2,000--5,000M (largest importers). Most developing countries $100--500M. Rich countries with domestic arms industries import less. Values are lumpy -- a single fighter jet deal can dominate a year.
- **Why it matters:** Reveals dependency relationships (who buys from whom) and military modernization patterns. Constant-price valuation makes time comparisons valid but the numbers don't correspond to actual procurement costs.

### Intentional homicides

- **Unit:** per 100,000 people
- **Source:** World Bank (`VC.IHR.PSRC.P5`)
- **What it measures:** Unlawful deaths purposefully inflicted by another person, per 100,000 population. Does not include conflict deaths.
- **Scale intuition:** 0.5--2 in East Asia and Western Europe. 3--6 in the USA. 10--20 in many African countries. 20--50+ in Latin America's worst-affected countries (El Salvador, Honduras, Venezuela). World average ~6.
- **Why it matters:** The single best proxy for everyday personal security. The massive range (100x between safest and most dangerous countries) is wider than almost any other social indicator. Latin America's outlier status relative to its income level is a key stylized fact.

### Refugees by country of origin

- **Unit:** thousands
- **Source:** World Bank (`SM.POP.RHCR.EO`)
- **What it measures:** People who have been forced to cross national borders to escape conflict, persecution, or disaster, counted by their home country.
- **Scale intuition:** Syria >6,000K. Afghanistan >2,500K. Ukraine >6,000K (post-2022). South Sudan ~2,000K. Most stable countries <10K. Highly concentrated -- a handful of conflicts drive most of the global total.
- **Why it matters:** A direct measure of state failure and conflict severity. The stock (total refugees) is sticky -- people don't return quickly even after conflicts end. Comparing origin vs. asylum figures reveals burden-sharing patterns.

### Refugees by country of asylum

- **Unit:** thousands
- **Source:** World Bank (`SM.POP.RHCR.EA`)
- **What it measures:** Same population, counted by the country hosting them.
- **Scale intuition:** Turkey >3,500K. Germany ~2,000K. Pakistan ~1,500K. Uganda ~1,500K. Most host countries are either neighbors of conflict zones or wealthy democracies with asylum systems.
- **Why it matters:** Reveals the distribution of hosting burden, which is heavily concentrated. Neighboring countries bear most of the load. The ratio of refugees to host-country population is more informative than the raw number for assessing political and fiscal strain.

---

## Finance & Markets

Macroeconomic and financial system indicators. Eras are 1960, 1990, and current.

### Inflation (CPI)

- **Unit:** annual %
- **Source:** World Bank (`FP.CPI.TOTL.ZG`)
- **What it measures:** Year-over-year change in consumer prices for a basket of goods and services.
- **Scale intuition:** 1--3% for well-anchored central banks (USA, Eurozone target ~2%). 5--10% in many developing countries. 20--100%+ in crisis episodes (Argentina, Turkey, Venezuela). 1960 values are often surprising -- many now-stable countries had high inflation.
- **Why it matters:** Probably the most asked-about macro variable in forecasting. The distribution is fat-tailed -- most countries cluster at 2--8% but extreme episodes are common. Historical values are especially useful for calibrating "how bad could it get" priors.

### Current account balance

- **Unit:** % of GDP
- **Source:** World Bank (`BN.CAB.XOKA.GD.ZS`)
- **What it measures:** Net trade in goods, services, and income flows. Positive = surplus (exporting more than importing). A country's saving-investment balance with the rest of the world.
- **Scale intuition:** +5 to +15% for oil exporters (Saudi Arabia, Russia). +3 to +8% for mercantilist exporters (Germany, South Korea). -2 to -5% for most developing countries and the USA. Ranges from roughly -15% to +25%.
- **Why it matters:** Persistent deficits signal reliance on foreign capital; persistent surpluses signal under-consumption. Sudden reversals ("sudden stops") are a classic trigger for financial crises. No regional aggregates available.

### Total reserves including gold

- **Unit:** billions of current US$
- **Source:** World Bank (`FI.RES.TOTL.CD`)
- **What it measures:** Foreign exchange reserves plus gold holdings at current prices, held by the central bank.
- **Scale intuition:** China ~$3,300B (largest by far). Japan ~$1,200B. India ~$600B. Russia ~$550B. Most developing countries $10--100B. Reserves-to-GDP or reserves-to-imports ratios are more informative than raw numbers.
- **Why it matters:** The war chest for defending a currency or absorbing external shocks. The rule of thumb for adequacy is 3 months of import cover, but the actual benchmark depends on capital account openness. Reserve accumulation patterns reveal central bank strategy and external vulnerability.
- **Note:** No regional aggregates available.

### Real interest rate

- **Unit:** %
- **Source:** World Bank (`FR.INR.RINR`)
- **What it measures:** Nominal lending interest rate minus inflation. The true cost of borrowing.
- **Scale intuition:** 0--3% in most stable economies during normal times. Negative during high-inflation episodes or financial repression. Can be 5--15%+ in tight-money developing countries. Historically volatile.
- **Why it matters:** The price of capital. Negative real rates transfer wealth from savers to borrowers (including governments with large debts). Cross-country differences reflect monetary policy credibility, institutional quality, and risk premia. No regional aggregates.

### Market capitalization (% of GDP)

- **Unit:** % of GDP
- **Source:** World Bank (`CM.MKT.LCAP.GD.ZS`)
- **What it measures:** Total value of listed domestic companies on the stock exchange as a share of GDP.
- **Scale intuition:** >100% for financial centers and tech-heavy markets (USA ~190%, South Korea ~100%). 30--70% for mid-size markets. <20% for many developing countries with thin equity markets.
- **Why it matters:** Proxy for financial depth and the role of equity markets in the economy. Very high ratios may signal overvaluation. Very low ratios suggest firms rely on bank lending or informal finance. Volatile year-to-year (moves with stock prices).

### Stocks traded (% of GDP)

- **Unit:** % of GDP
- **Source:** World Bank (`CM.MKT.TRAD.GD.ZS`)
- **What it measures:** Total value of shares traded on the stock exchange during the year, as a share of GDP. A liquidity measure.
- **Scale intuition:** >100% for the most liquid markets (USA, China). 20--60% for mid-size markets. <10% for illiquid frontier markets. Much more volatile than market cap -- trading surges in bull markets.
- **Why it matters:** Complements market capitalization. A market can be large (high cap) but illiquid (low turnover), which matters for price discovery, risk management, and capital allocation efficiency.

### Domestic credit to private sector

- **Unit:** % of GDP
- **Source:** World Bank (`FS.AST.PRVT.GD.ZS`)
- **What it measures:** Financial resources provided to the private sector by banks and other financial institutions, as a share of GDP. The broadest measure of bank-intermediated finance.
- **Scale intuition:** >150% for deeply banked economies (USA ~200%, Japan ~170%). 50--100% for most middle-income countries. <30% in the poorest countries (Sub-Saharan Africa average ~30%). China ~180% reflecting its bank-dominated financial system.
- **Why it matters:** The best single indicator of financial depth. Rapid credit growth (>10 percentage points/year) is one of the strongest predictors of future banking crises. Low levels indicate underdeveloped financial systems where firms rely on retained earnings or informal lending.

### Personal remittances received

- **Unit:** billions of current US$
- **Source:** World Bank (`BX.TRF.PWKR.CD.DT`)
- **What it measures:** Personal transfers and compensation of employees received from abroad. Money sent home by migrant workers.
- **Scale intuition:** India ~$115B (largest recipient). Mexico ~$60B. Philippines ~$40B. Egypt ~$30B. Small amounts for rich countries that are net senders. Remittances exceed ODA for most developing countries.
- **Why it matters:** For many developing countries, remittances are a larger and more stable source of foreign exchange than foreign aid or FDI. Countercyclical in the origin country (migrants send more when home country is in crisis), which provides a natural stabilizer. The remittance-to-GDP ratio is more informative for small economies.

---

## Education

Human capital formation indicators. Eras are 1990 and current.

### Adult literacy rate

- **Unit:** % of people ages 15+
- **Source:** World Bank (`SE.ADT.LITR.ZS`)
- **What it measures:** Share of the adult population that can read and write a short simple statement about their everyday life.
- **Scale intuition:** >99% in rich countries (effectively universal). 70--95% in most middle-income countries. 30--60% in some Sub-Saharan African countries (Niger ~35%). Gender gaps are large in South Asia and West Africa.
- **Why it matters:** A floor indicator -- it distinguishes very low-development contexts but provides little differentiation among middle-income and above. The trajectory from 1990 to current shows where mass education investments have paid off. Data can be patchy (census-dependent).

### Secondary school enrollment

- **Unit:** % gross enrollment ratio
- **Source:** World Bank (`SE.SEC.ENRR`)
- **What it measures:** Total enrollment in secondary education regardless of age, expressed as a percentage of the population of official secondary school age. Can exceed 100% due to over-age or repeating students.
- **Scale intuition:** >100% in many rich countries (over-age enrollment). 70--100% in most middle-income countries. 20--50% in the poorest countries (Sub-Saharan Africa average ~50%). Values above 100% are normal and expected.
- **Why it matters:** The most informative education indicator for middle-income countries. The gap between primary (near-universal in most places) and secondary enrollment reveals where the education pipeline leaks. Strongly predicts workforce quality 10--15 years out.

### Tertiary school enrollment

- **Unit:** % gross enrollment ratio
- **Source:** World Bank (`SE.TER.ENRR`)
- **What it measures:** Same as secondary but for university/college-level education.
- **Scale intuition:** 80--100%+ in rich countries with mass higher education (South Korea ~98%, USA ~88%). 30--60% in middle-income countries. <10% in many low-income countries (Sub-Saharan Africa average ~10%).
- **Why it matters:** The widest education gap between rich and poor countries. High enrollment doesn't guarantee quality, but it does predict the supply of skilled workers, innovation capacity, and institutional complexity. The 1990-to-current expansion in East Asia is particularly striking.

### Government education expenditure

- **Unit:** % of GDP
- **Source:** World Bank (`SE.XPD.TOTL.GD.ZS`)
- **What it measures:** Total government spending on education (all levels) as a share of GDP.
- **Scale intuition:** 5--7% for high-spending countries (Nordics, some small states). 3--5% for most countries. <3% in countries that underfund education (many conflict-affected states). World average ~4.5%.
- **Why it matters:** Spending levels alone don't predict outcomes (efficiency matters enormously), but persistently low spending is a reliable predictor of poor outcomes. The variation is narrower than you might expect -- most countries spend 3--6% regardless of income level.

---

## Governance

Worldwide Governance Indicators (WGI) from the World Bank. All six use the same scale. Eras are 2000 and current.

**Common scale for all governance indicators:**
- **Unit:** index from -2.5 (worst) to +2.5 (best)
- **Interpretation:** 0 is roughly the global median. Standard deviation ~1.0. The scale is derived from aggregating dozens of underlying data sources (expert surveys, citizen polls, NGO assessments).
- **Scale intuition:** +1.5 to +2.5 for top performers (Nordics, Singapore, New Zealand). +0.5 to +1.5 for most OECD. -0.5 to +0.5 for mid-range developing countries. -1.0 to -2.0 for fragile and conflict-affected states.
- **Note:** No regional aggregates available for any governance indicator.

### Government effectiveness

- **Source:** World Bank (`GE.EST`)
- **What it measures:** Quality of public services, civil service independence from political pressure, quality of policy formulation and implementation, and government credibility.
- **Why it matters:** The most "administrative" of the six. Predicts a government's ability to actually deliver on its stated policies. Singapore scores very high here despite scoring lower on voice/accountability -- a useful illustration that the six dimensions capture different things.

### Control of corruption

- **Source:** World Bank (`CC.EST`)
- **What it measures:** Perceptions of the extent to which public power is exercised for private gain, including both petty and grand corruption and state capture.
- **Why it matters:** One of the strongest predictors of investment climate and aid effectiveness. Highly persistent -- countries rarely move more than 0.3 points per decade. The correlation with GDP per capita is strong but there are notable outliers (China: high growth despite middling corruption scores).

### Rule of law

- **Source:** World Bank (`RL.EST`)
- **What it measures:** Perceptions of the extent to which agents have confidence in and abide by the rules of society -- contract enforcement, property rights, police, courts, and the likelihood of crime and violence.
- **Why it matters:** The closest proxy for "institutional quality" as used in the economics literature. Predicts FDI flows, business formation, and long-run growth better than most policy variables. The gap between formal laws on the books and actual enforcement is what this captures.

### Regulatory quality

- **Source:** World Bank (`RQ.EST`)
- **What it measures:** Perceptions of the government's ability to formulate and implement sound policies and regulations that permit and promote private sector development.
- **Why it matters:** Captures the business environment -- licensing, trade barriers, price controls, and the overall ease of doing business. High-regulation countries can score well if the regulations are well-designed and consistently applied.

### Voice and accountability

- **Source:** World Bank (`VA.EST`)
- **What it measures:** Perceptions of the extent to which citizens can participate in selecting their government, as well as freedom of expression, freedom of association, and free media.
- **Why it matters:** The most "political" dimension. Correlates with but is distinct from democracy indices (Freedom House, Polity). Captures the expressive and participatory dimensions that matter for forecasting political stability, protest risk, and regime change.

### Political stability

- **Source:** World Bank (`PV.EST`)
- **What it measures:** Perceptions of the likelihood of political instability and/or politically motivated violence, including terrorism.
- **Why it matters:** The most volatile of the six governance indicators. Directly relevant for forecasting conflict risk, coup risk, and civil unrest. Countries can score well on other governance dimensions while scoring poorly here (e.g., Turkey: decent regulatory quality but low political stability).

---

## Urban Areas

City-level data from the GHS Urban Centre Database (GHS-UCDB), covering the world's 50 largest cities by 2025 population plus income-group aggregates. Eras are 1990, 2000, 2010, 2020, and 2025 (where available).

### Population (city)

- **Unit:** millions
- **Source:** GHS-UCDB (`GH_POP_TOT`)
- **What it measures:** Total population within the urban centre boundary as defined by the GHSL built-up area methodology. Not the same as administrative city boundaries (usually larger).
- **Scale intuition:** Guangzhou ~65M (the GHSL definition captures the Pearl River Delta megacity). Tokyo ~37M. Jakarta ~35M. Most top-50 cities are 10--25M. Aggregates: All Cities median ~15M.
- **Why it matters:** City populations are notoriously definition-dependent. The GHSL satellite-derived boundaries provide consistent cross-city comparisons but can differ dramatically from official figures. Understanding which definition is being used is critical for interpreting any urban statistic.

### CO2 emissions per capita (city)

- **Unit:** tonnes per person
- **Source:** GHS-UCDB (`EM_CO2_PEC`)
- **What it measures:** Urban-area CO2 emissions per person, estimated from downscaled national emissions data combined with spatial proxies.
- **Scale intuition:** 1--3 tonnes for South Asian cities. 3--8 for East Asian and Latin American cities. 10--20+ for cities in high-income countries (Los Angeles ~15). Higher than national averages for some developing-country cities due to industry concentration.
- **Why it matters:** Urbanization is both a driver of emissions (transport, construction) and a mitigator (density, shared infrastructure). Comparing city-level to national per-capita emissions reveals whether urbanization is net-positive or net-negative for climate in a given context.

### PM2.5 concentration

- **Unit:** micrograms per cubic meter (ug/m3)
- **Source:** GHS-UCDB (`EM_PM2_CON`)
- **What it measures:** Annual mean concentration of fine particulate matter (particles <2.5 micrometers). The most health-relevant air quality metric.
- **Scale intuition:** WHO guideline is 5 ug/m3 (almost no city meets this). 10--15 in clean cities (Tokyo, London). 30--60 in moderately polluted cities (Mexico City, Bangkok). 80--120+ in severely polluted cities (Delhi, Dhaka, Lahore). Available from 2000 onward.
- **Why it matters:** The air pollution metric with the strongest health evidence. Responsible for millions of premature deaths annually. The 2000-to-2020 trajectory is mixed -- improving in some cities (Beijing), worsening in others (African cities). A key quality-of-life indicator for rapidly urbanizing regions.

### Life expectancy (city)

- **Unit:** years
- **Source:** GHS-UCDB (`SC_SEC_LET`)
- **What it measures:** City-level life expectancy, estimated from subnational health data and demographic models.
- **Scale intuition:** 80--85 for cities in rich countries. 70--78 for middle-income-country cities. 55--65 for cities in the poorest countries (Kinshasa ~60, Lagos ~55). Generally higher than national averages due to better healthcare access.
- **Why it matters:** The urban advantage in health is real but not universal -- some very large developing-country cities have life expectancy below their national average due to slum conditions, pollution, and overcrowding. Comparing city to national values is informative.

### Built-up area per capita

- **Unit:** m2 per person
- **Source:** GHS-UCDB (`GH_BPC_TOT`)
- **What it measures:** Total built-up area (buildings, roads, paved surfaces) divided by population. A satellite-derived density proxy.
- **Scale intuition:** 20--40 m2 for very dense cities (Dhaka ~15, Mumbai ~20). 50--100 for mid-density (Beijing, Mexico City). 150--300+ for sprawling cities (Los Angeles ~200). High-income cities are consistently less dense.
- **Why it matters:** The physical footprint of urbanization. Declining per-capita built-up area means densification (common in fast-growing developing-country cities). Rising values mean sprawl. Has implications for transport energy use, infrastructure costs, and livability.

### Human Development Index (city)

- **Unit:** index from 0 to 1
- **Source:** GHS-UCDB (`SC_SEC_HDI`)
- **What it measures:** Composite index of life expectancy, education, and income, adapted to the city level from subnational data.
- **Scale intuition:** 0.90--0.95 for cities in rich countries (Tokyo, London, Paris). 0.70--0.85 for middle-income-country cities. 0.40--0.60 for cities in the poorest countries (Kinshasa ~0.47). Generally higher than national HDI.
- **Why it matters:** Summarizes multidimensional welfare in a single number. The within-country city-vs-national gap reveals urban advantage. Useful as a composite anchor when you're unsure about individual sub-indicators for a city.

---

## Descriptive Statistics

Not a separate set of indicators. This deck generates cards from the mean, median, and standard deviation of each indicator across entities in a given era. It covers all source decks (development, tech adoption, conflict & security, finance, education, governance, urban areas).

- **Card types:** "What is the mean/median/SD of [indicator] across [entity group] in [year]?"
- **Why it matters:** Knowing the cross-country distribution -- not just individual country values -- is essential for calibration. If you know that GDP per capita has a mean of $20,000 and an SD of $18,000, you know the distribution is right-skewed and can set better confidence intervals for unfamiliar countries.
