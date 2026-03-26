"""
Deck builder: generates an Anki .apkg file from CSV data files.

Reads CSVs produced by fetch_data, generates questions with reference
comparisons, and packages them into a genanki deck using the Interval
(Anki with Uncertainty) card model.
"""

from __future__ import annotations

from pathlib import Path

import genanki
import polars as pl

from knowledge_base.config import DECKS, ENTITIES

# ---------------------------------------------------------------------------
# Anki card templates
# ---------------------------------------------------------------------------

QFMT = r"""{{Front}}

<br/>
<br/>

<p style="font-size: medium">Give your <span style="font-weight: bold;" id="confidence-interval"></span> confidence interval:</p>

<input id="interval" autofocus style="min-width: 50%; text-align: center; font-size: large" type="text" />
<label style="display:block; opacity: .4; font-size: small; padding-top: 10px" for="interval">
	❔ Enter a range ("1-10") or write the exact answer ("6").
</label>

<script>

var possibleIntervals = [50, 60, 70, 80, 90, 95]
window.CONFIDENCE_INTERVAL = possibleIntervals[Math.floor(Math.random() * possibleIntervals.length)]
document.querySelector("#confidence-interval").textContent = `${window.CONFIDENCE_INTERVAL}%`

var intervalInput = document.querySelector("#interval")
intervalInput.addEventListener(
	"change",
	(e) => {
		window.INTERVAL_TEXT = e.target.value
	}
)
intervalInput.addEventListener("keypress", (e) => {
	if (event.key === "Enter") {
		window.bridgeCommand("ans")
	}
})

setInterval(() => document.querySelector("#interval")?.focus(), 50)

document.addEventListener("DOMContentLoaded", function(event) {
	document.focus()
	setTimeout(() => document.querySelector("#interval").focus(), 50)
})

</script>"""

AFMT = r"""{{Front}}

<p id="youSaid"><i class="hint">You said: </i><span id="intervalTextDisplay"></span></p>

<hr style="opacity:0.3" id="answer">

<p><i class="hint">Answer:</i> {{Answer (must be a number)}}</p>

<p class="hint">{{Notes}}</p>

<div id="errorContainer">
	<p id="error" style="color:red"></p>
</div>

<p id="intervalResults"></p>

<p id="accuracyDisplay" class="hint intervalBack" style="font-size: small;">Desired accuracy multiplier: <span id="accuracySpan"></span></p>

<div class="intervalBack" style="position: absolute; left: 50%; transform: translateX(-50%); bottom: 5px; background: grey; padding: 0 20px; display: flex; font-weight: bold" title="Based on your score, we recommend you select this difficulty. Get a higher score to see this card less often.">
	<p id="buttonHint"></p>
</div>


<script>
	function setError(errStr) {
		document.querySelector("#error").textContent = errStr
	}

	document.querySelector("#intervalTextDisplay").textContent = window.INTERVAL_TEXT

	if (!window.INTERVAL_TEXT) {
		setError("You didn't type an answer")
		document.querySelector("#youSaid").style = "display: none"
  	document.querySelectorAll(".intervalBack").forEach((el) => el.style = "display:none")
	} else {

		var interval = window.INTERVAL_TEXT

		// Parse range, handling negative numbers (e.g., "-6--2", "-3-5", "3-10")
		var rangeMatch = interval.match(/^\s*(-?\d+\.?\d*)\s*-\s*(-?\d+\.?\d*)\s*$/)
		var parts = rangeMatch ? [rangeMatch[1], rangeMatch[2]] : [interval.trim()]

		var accuracyMultiplier = String.raw`{{Desired accuracy multiplier}}` || "1"

		if (parts.length === 2) {
			if (isNaN(String.raw`{{Answer (must be a number)}}`)) {
				setError("Error: card back is not numerical: {{Answer (must be a number)}}")
			}
			else if (isNaN(parts[0])) {
				setError("Error: lower bound is not numerical: " + parts[0])
			} else if (isNaN(parts[1])) {
				setError("Error: upper bound is not numerical: " + parts[1])
			} else if (!CONFIDENCE_INTERVAL) {
				setError("Plugin error: missing confidence interval")
			} else if (isNaN(accuracyMultiplier) || accuracyMultiplier <= 0) {
				setError("Error: desired accuracy multiplier must be a positive number. 1 = default, 2 = high accuracy, 0.5 = low accuracy.")
			} else {
				var lower = Number(parts[0])
				var upper = Number(parts[1])
				var answer = Number(String.raw`{{Answer (must be a number)}}`)

				var results = document.querySelector("#intervalResults")

				var correct = answer >= lower && answer <= upper
				if (correct) {
					results.textContent = "✅ Correct!"
					results.style = "background: darkgreen; padding: 5px"
				} else {
					results.textContent = "🔴 Incorrect!"
					results.style = "background: darkred; padding: 5px"
				}

				var useLogScoring = answer >= 10000
				var score = ankiScore(lower, upper, answer, window.CONFIDENCE_INTERVAL, useLogScoring, 1000)
				results.textContent += ` ${score > 0 ? "+" : ""}${score.toPrecision(2)} points`

				if (accuracyMultiplier == 1) {
					document.querySelector("#accuracyDisplay").style = "display:none"
				} else {
					document.querySelector("#accuracySpan").textContent = accuracyMultiplier
				}

				var recommendation = score < 0 ? "Again [1]" : ( score < (2 * accuracyMultiplier) ? "Hard [2]" : ( score < (4 * accuracyMultiplier) ? "Good [3]" : "Easy [4]" ) )
				document.querySelector("#buttonHint").textContent = `${recommendation}`

				var calibrationData = {
					correct,
					confidenceInterval: window.CONFIDENCE_INTERVAL,
					score,
					timestamp: new Date(),
					question: String.raw`{{Front}}`.replace("\\n", ""),
				}
				window.bridgeCommand(`updateCalibration;${JSON.stringify(calibrationData)}`)
			}

		} else {
			document.querySelectorAll(".intervalBack").forEach((el) => el.style = "display:none")
		}

	}


function ankiScore(
  lowerBound,
  upperBound,
  answer,
  confidenceInterval,
  useLogScoring,
  C,
) {
  const SMAX = 10;
  const SMIN = -50; // higher lower bound for challenge questions to be more forgiving
  const DELTA = 0.4;
  const EPSILON = 0.0000000001;
  const B = confidenceInterval / 100;

  return greenbergScoring(lowerBound,
    upperBound,
    answer,
    useLogScoring,
    C,
    SMAX,
    SMIN,
    DELTA,
    EPSILON,
    B,
  )
}

function greenbergScoring(
  lowerBound,
  upperBound,
  answer,
  useLogScoring,
  C,
  SMAX,
  SMIN,
  DELTA,
  EPSILON,
  B,
) {
  if (!useLogScoring) {
    lowerBound -= EPSILON;
    upperBound += EPSILON;
    let r = (lowerBound - answer) / C;
    let s = (upperBound - lowerBound) / C;
    let t = (answer - upperBound) / C;
    if (answer < lowerBound) {
      return Math.max(SMIN, (-2 / (1 - B)) * r - (r / (1 + r)) * s);
    } else if (answer > upperBound) {
      return Math.max(SMIN, (-2 / (1 - B)) * t - (t / (1 + t)) * s);
    }
    lowerBound -= DELTA;
    upperBound += DELTA;
    r = (lowerBound - answer) / C;
    s = (upperBound - lowerBound) / C;
    t = (answer - upperBound) / C;
    return ((4 * SMAX * r * t) / (s * s)) * (1 - s / (1 + s));
  } else {
    lowerBound /= 10 ** EPSILON;
    upperBound *= 10 ** EPSILON;
    let r = Math.log(lowerBound / answer) / Math.log(C);
    let s = Math.log(upperBound / lowerBound) / Math.log(C);
    let t = Math.log(answer / upperBound) / Math.log(C);
    if (answer < lowerBound) {
      return Math.max(SMIN, (-2 / (1 - B)) * r - (r / (1 + r)) * s);
    } else if (answer > upperBound) {
      return Math.max(SMIN, (-2 / (1 - B)) * t - (t / (1 + t)) * s);
    }
    lowerBound /= 10 ** DELTA;
    upperBound *= 10 ** DELTA;
    r = Math.log(lowerBound / answer) / Math.log(C);
    s = Math.log(upperBound / lowerBound) / Math.log(C);
    t = Math.log(answer / upperBound) / Math.log(C);
    return ((4 * SMAX * r * t) / (s * s)) * (1 - s / (1 + s));
  }
};

</script>"""

CSS = """.card {
    font-family: arial;
    font-size: 20px;
    text-align: center;
    color: black;
    background-color: white;
}

.hint {
	opacity: 0.6
}"""

# ---------------------------------------------------------------------------
# Genanki model and deck
# ---------------------------------------------------------------------------

INTERVAL_MODEL = genanki.Model(
    1677887272395,
    "Interval",
    fields=[
        {"name": "Front"},
        {"name": "Answer (must be a number)"},
        {"name": "Notes"},
        {"name": "Desired accuracy multiplier"},
    ],
    templates=[
        {
            "name": "Card 1",
            "qfmt": QFMT,
            "afmt": AFMT,
        }
    ],
    css=CSS,
)

# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


def compute_reference_averages(
    df: pl.DataFrame,
    era: str,
    reference_entity: str = "World",
    reference_entity_type: str = "region",
) -> tuple[float | None, dict[str, float]]:
    """Extract reference entity value as world_avg and same-type rows as a dict.

    Returns (world_avg, region_avgs) where region_avgs maps entity name
    to its aggregate value for the given era.
    """
    era_df = df.filter(pl.col("era") == era)

    # World average
    world_rows = era_df.filter(pl.col("entity") == reference_entity)
    world_avg: float | None = None
    if len(world_rows) > 0:
        world_avg = world_rows["value"][0]

    # Regional averages
    region_rows = era_df.filter(
        (pl.col("entity_type") == reference_entity_type) & (pl.col("entity") != reference_entity)
    )
    region_avgs: dict[str, float] = {}
    for row in region_rows.iter_rows(named=True):
        region_avgs[row["entity"]] = row["value"]

    return world_avg, region_avgs


def format_answer(value: float, indicator: dict) -> str:
    """Round and format a numerical answer for the card."""
    scale_factor = indicator.get("scale_factor", 1)
    decimals = indicator.get("decimals", 1)
    scaled = value / scale_factor
    rounded = round(scaled, decimals)
    if decimals == 0:
        return str(int(rounded))
    return f"{rounded:.{decimals}f}"


def generate_question(
    entity: str,
    indicator_name: str,
    year: int,
    unit_label: str,
    era: str,
) -> str:
    """Produce the Front field for an Anki card.

    Uses "What is...as of {year}" for current era,
    "What was...in {year}" for historical eras.
    """
    if era == "current":
        return (
            f"What is {entity}'s {indicator_name} as of {year}, {unit_label}?"
        )
    else:
        return (
            f"What was {entity}'s {indicator_name} in {year}, {unit_label}?"
        )


def _format_number(
    value: float | int, prefix: str = "", decimals: int = 0
) -> str:
    """Format a number with commas and an optional prefix."""
    if decimals == 0:
        return f"{prefix}{value:,.0f}"
    return f"{prefix}{value:,.{decimals}f}"


def generate_notes(
    source: str,
    world_avg: float | None,
    regional_avg: float | None,
    unit_prefix: str = "",
    decimals: int = 0,
) -> str:
    """Produce the Notes field with source and reference comparisons.

    Includes world average and (if available) regional average,
    formatted with commas and the unit prefix.
    """
    parts = [f"Source: {source}"]
    if world_avg is not None:
        formatted_world = _format_number(world_avg, unit_prefix, decimals)
        if regional_avg is not None:
            formatted_regional = _format_number(
                regional_avg, unit_prefix, decimals
            )
            parts.append(
                f"World avg: {formatted_world}, regional avg: {formatted_regional}"
            )
        else:
            parts.append(f"World avg: {formatted_world}")
    return " | ".join(parts)


def generate_notes_land_area(
    source: str,
    reference_total: int | float,
) -> str:
    """Produce the Notes field for land area cards."""
    formatted_total = f"{reference_total:,.0f}"
    return f"Source: {source} | Reference total: {formatted_total} km\u00b2"


def build_tags(
    category: str,
    indicator_id: str,
    entity_slug: str,
    entity_type: str,
    era: str,
) -> list[str]:
    """Return a list of tag strings for an Anki note."""
    return [
        f"category::{category}",
        f"indicator::{indicator_id}",
        f"entity::{entity_slug}",
        f"entity_type::{entity_type}",
        f"era::{era}",
    ]


def _find_entity_config(entity_name: str, entities: list[dict] | None = None) -> dict | None:
    """Look up entity config by name from the given entity list."""
    for e in (entities or ENTITIES):
        if e["name"] == entity_name:
            return e
    return None


def _run(
    deck_key: str,
    data_dir: Path | None = None,
    output_path: Path | None = None,
) -> None:
    """Build the Anki deck from CSV data files.

    Reads each CSV from data_dir, matches filenames to indicator configs,
    generates cards, and writes the .apkg file.
    """
    if deck_key not in DECKS:
        raise KeyError(f"Unknown deck key: {deck_key!r}. Available: {list(DECKS)}")

    deck_cfg = DECKS[deck_key]
    entities = deck_cfg.get("entities", ENTITIES)
    ref_entity = deck_cfg.get("reference_entity", "World")
    ref_entity_type = deck_cfg.get("reference_entity_type", "region")
    indicator_by_id = {ind["id"]: ind for ind in deck_cfg["indicators"]}
    resolved_data_dir = data_dir or Path(deck_cfg["data_dir"])
    resolved_output_path = output_path or Path(deck_cfg["output"])

    deck = genanki.Deck(deck_cfg["deck_id"], deck_cfg["name"])

    csv_files = sorted(resolved_data_dir.glob("*.csv"))

    for csv_path in csv_files:
        indicator_id = csv_path.stem
        indicator = indicator_by_id.get(indicator_id)
        if indicator is None:
            continue

        df = pl.read_csv(csv_path)
        unit_prefix = indicator.get("unit_prefix", "")
        is_land_area = indicator_id == "land_area"

        # Compute reference averages per era
        eras = df["era"].unique().to_list()
        ref_by_era: dict[str, tuple[float | None, dict[str, float]]] = {}
        for era in eras:
            ref_by_era[era] = compute_reference_averages(
                df, era,
                reference_entity=ref_entity,
                reference_entity_type=ref_entity_type,
            )

        # Filter to non-region/non-aggregate rows for card generation
        card_rows = df.filter(
            ~pl.col("entity_type").is_in(["region", "aggregate"])
        )

        for row in card_rows.iter_rows(named=True):
            entity_name = row["entity"]
            entity_cfg = _find_entity_config(entity_name, entities)
            if entity_cfg is None:
                continue

            era = row["era"]
            year = row["year"]
            value = row["value"]
            source = row["source"]
            entity_slug = entity_cfg["tag_slug"]
            entity_type = entity_cfg["entity_type"]

            # Generate question
            question = generate_question(
                entity=entity_name,
                indicator_name=indicator["name"],
                year=year,
                unit_label=indicator["unit_label"],
                era=era,
            )

            # Generate notes
            if is_land_area:
                world_avg, region_avgs = ref_by_era.get(
                    era, (None, {})
                )
                region_name = entity_cfg.get("region", "")
                reference_total = region_avgs.get(
                    region_name, world_avg or 0
                )
                notes = generate_notes_land_area(
                    source=source,
                    reference_total=reference_total,
                )
            else:
                world_avg, region_avgs = ref_by_era.get(
                    era, (None, {})
                )
                region_name = entity_cfg.get("region", "")
                regional_avg = region_avgs.get(region_name)
                scale_factor = indicator.get("scale_factor", 1)
                scaled_world = world_avg / scale_factor if world_avg is not None else None
                scaled_regional = regional_avg / scale_factor if regional_avg is not None else None
                notes = generate_notes(
                    source=source,
                    world_avg=scaled_world,
                    regional_avg=scaled_regional,
                    unit_prefix=unit_prefix,
                    decimals=indicator.get("decimals", 1),
                )

            # Build tags
            tags = build_tags(
                category=indicator["category"],
                indicator_id=indicator_id,
                entity_slug=entity_slug,
                entity_type=entity_type,
                era=era,
            )

            # Create genanki Note
            note = genanki.Note(
                model=INTERVAL_MODEL,
                fields=[
                    question,
                    format_answer(value, indicator),
                    notes,
                    "2",  # Desired accuracy multiplier
                ],
                tags=tags,
            )
            deck.add_note(note)

    package = genanki.Package(deck)
    package.write_to_file(str(resolved_output_path))


def main() -> None:
    """CLI entry point: build a deck by key."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: build-deck <deck_key>")
        print(f"Available decks: {', '.join(DECKS)}")
        raise SystemExit(1)
    _run(sys.argv[1])
