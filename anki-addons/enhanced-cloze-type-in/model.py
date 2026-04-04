import re
from copy import deepcopy
from typing import Optional, Tuple

from aqt import mw
from aqt.gui_hooks import profile_did_open, sync_did_finish

from .constants import MODEL_NAME, NOTE_TYPE_DIR
from .note_type.model import enhancedModel
from .compat import add_compatibility_aliases

try:
    from aqt.models import NotetypeDict
except Exception:
    pass


def setup_maybe_update_model_on_startup() -> None:
    def on_profile_did_open():
        add_compatibility_aliases()

        if not mw.can_auto_sync():
            add_or_update_model()
        else:
            def fn():
                add_or_update_model()
                sync_did_finish.remove(fn)

            sync_did_finish.append(fn)

    profile_did_open.append(on_profile_did_open)


def _new_version_available() -> bool:
    return current_version() is None or current_version() < incoming_version()


def current_version() -> Optional[Tuple[int, ...]]:
    return version(mw.col.models.by_name(MODEL_NAME))


def incoming_version() -> Optional[Tuple[int, ...]]:
    return version(enhanced_cloze())


def version(note_type: "NotetypeDict") -> Optional[Tuple[int, ...]]:
    front = note_type["tmpls"][0]["qfmt"]
    m = re.match("<!-- VERSION (.+?) -->", front)
    if not m:
        return None
    return tuple(map(int, m.group(1).split(".")))


def set_version(front: str, ver: Tuple[int, ...]) -> str:
    return re.sub(
        "<!-- VERSION (.+?) -->",
        f"<!-- VERSION {'.'.join(map(str, ver))} -->",
        front,
    )


def add_or_update_model() -> None:
    model = mw.col.models.by_name(MODEL_NAME)
    if not model:
        mw.col.models.add(enhanced_cloze())
        return

    if not _new_version_available():
        return

    seperator = "<!-- ENHANCED_CLOZE_TYPE_IN -->"
    cur_front = model["tmpls"][0]["qfmt"]
    incoming_front = enhanced_cloze()["tmpls"][0]["qfmt"]

    cur_sep_m = re.search(seperator, cur_front)
    if not cur_sep_m:
        model["tmpls"][0]["qfmt"] = incoming_front
    else:
        incoming_sep_m = re.search(seperator, incoming_front)
        cur_before_sep = cur_front[: cur_sep_m.start()]
        incoming_after_sep = incoming_front[incoming_sep_m.end():]
        new_front = f"{cur_before_sep}{seperator}{incoming_after_sep}"
        new_front = set_version(new_front, incoming_version())
        model["tmpls"][0]["qfmt"] = new_front

    model["tmpls"][0]["afmt"] = enhanced_cloze()["tmpls"][0]["afmt"]
    model["css"] = enhanced_cloze()["css"]
    mw.col.models.update_dict(model)


def enhanced_cloze() -> "NotetypeDict":
    result = deepcopy(enhancedModel)
    load_enhanced_cloze(result)
    return result


def load_enhanced_cloze(note_type: "NotetypeDict") -> None:
    front_path = NOTE_TYPE_DIR / "Enhanced_Cloze_TypeIn_Front_Side.html"
    css_path = NOTE_TYPE_DIR / "Enhanced_Cloze_TypeIn_CSS.css"
    back_path = NOTE_TYPE_DIR / "Enhanced_Cloze_TypeIn_Back_Side.html"

    with open(front_path) as f:
        front = f.read()
    with open(back_path) as f:
        back = f.read()
    with open(css_path) as f:
        styling = f.read()

    note_type["tmpls"][0]["qfmt"] = front
    note_type["tmpls"][0]["afmt"] = back
    note_type["css"] = styling


def update_model_options_with_config_values() -> None:
    from .config import conf

    conf_lines = []
    for key in conf:
        value = conf[key]
        if isinstance(value, str):
            value = f'"{value}"'
        elif isinstance(value, bool):
            value = "true" if value else "false"
        conf_lines.append(f"var {key}={value}")
    conf_str = "\n".join(conf_lines)

    model = mw.col.models.by_name(MODEL_NAME)
    front = model["tmpls"][0]["qfmt"]
    front = re.sub(
        r"<script>[\w\W]*?</script>(?=\n<!-- CONFIG END -->)",
        f"<script>\n{conf_str}\n</script>",
        front,
    )
    assert conf_str in front, "Could not update note type options"
    model["tmpls"][0]["qfmt"] = front
    mw.col.models.update_dict(model)
