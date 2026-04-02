from aqt import mw
from aqt.gui_hooks import main_window_did_init
from aqt.qt import QMenu
from aqt.utils import askUser, qconnect, tooltip

from .constants import MODEL_NAME
from .model import add_or_update_model, enhanced_cloze


def setup_enhanced_cloze_menu() -> None:
    def on_main_window_did_init():
        menu: QMenu = mw.form.menuTools
        submenu = menu.addMenu("Enhanced Cloze Type-In")
        add_reset_notetype_action_to_menu(submenu)
        add_reset_css_action_to_menu(submenu)

    main_window_did_init.append(on_main_window_did_init)


def add_reset_notetype_action_to_menu(menu: QMenu) -> None:
    action = menu.addAction("Reset note type")

    def on_triggered():
        if not askUser(
            "This will reset the Enhanced Cloze Type-In note type to its default version.\n\n"
            "Note: After doing this the next time you synchronize Anki will require a full sync to AnkiWeb.\n\n"
            "Continue?",
        ):
            return

        current_model = mw.col.models.by_name(MODEL_NAME)
        if not current_model:
            add_or_update_model()
            return

        default_model = enhanced_cloze()
        default_model["id"] = current_model["id"]
        default_model["usn"] = -1
        mw.col.models.update_dict(default_model)
        tooltip("Successfully reset Enhanced Cloze Type-In note type.")

    qconnect(action.triggered, on_triggered)


def add_reset_css_action_to_menu(menu: QMenu) -> None:
    action = menu.addAction("Reset note type styling (css)")

    def on_triggered() -> None:
        if not askUser(
            "This will reset the styling (css) of the Enhanced Cloze Type-In note type to its default version.\n\nContinue?"
        ):
            return

        current_model = mw.col.models.by_name(MODEL_NAME)
        if not current_model:
            add_or_update_model()
            return

        current_model["css"] = enhanced_cloze()["css"]
        mw.col.models.update_dict(current_model)
        tooltip("Successfully reset Enhanced Cloze Type-In note type styling.")

    qconnect(action.triggered, on_triggered)
