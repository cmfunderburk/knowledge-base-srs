from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

INTERVALS: dict[int, int] = {1: 1, 2: 2, 3: 4, 4: 8, 5: 16}
MAX_BOX = 5


@dataclass
class LeitnerResult:
    box: int
    interval: float  # days
    due: str         # ISO-8601


def schedule(current_box: int, grade: int, now: datetime) -> LeitnerResult:
    """Map a grade to a new Leitner box and compute next due date.

    grade: 1=Again (box 1), 2=Hard (stay), 3=Good (next), 4=Easy (+2 boxes)
    """
    if current_box not in INTERVALS:
        raise ValueError(f"current_box must be 1-5, got {current_box}")
    if grade not in (1, 2, 3, 4):
        raise ValueError(f"grade must be 1-4, got {grade}")

    if grade == 1:
        new_box = 1
    elif grade == 2:
        new_box = current_box
    elif grade == 3:
        new_box = min(current_box + 1, MAX_BOX)
    else:
        new_box = min(current_box + 2, MAX_BOX)

    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    interval = float(INTERVALS[new_box])
    due = (now + timedelta(days=interval)).isoformat()
    return LeitnerResult(box=new_box, interval=interval, due=due)
