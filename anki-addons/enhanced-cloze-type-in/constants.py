from pathlib import Path

from anki.buildinfo import version as anki_version
from .lib.packaging.version import Version  # type: ignore

MODEL_NAME = "Enhanced Cloze Type-In 1.0"
ANKI_VERSION = Version(anki_version)
NOTE_TYPE_DIR = Path(__file__).parent / "note_type"
