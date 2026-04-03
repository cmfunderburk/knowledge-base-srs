"""Catalog tree builder, selection logic, and TUI screen for generation cards.

Provides CatalogNode (a tree node with selection and card-ID collection),
build_tree (constructs the deck -> topic -> source -> section hierarchy from
the database), and CatalogScreen (a Textual Screen for browsing and selecting
cards to practice).
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Footer, Header, Static, Tree
from rich.text import Text


@dataclass
class CatalogNode:
    """A node in the catalog selection tree."""

    label: str
    node_type: str  # "deck", "topic", "source", "section"
    card_count: int = 0
    children: list[CatalogNode] = field(default_factory=list)
    selected: bool = False

    # Optional identifiers for filtering
    deck: str | None = None
    topic_id: str | None = None
    source: str | None = None
    section_id: str | None = None
    section_title: str | None = None

    # Card IDs at leaf level
    _card_ids: list[int] = field(default_factory=list)

    def set_selected(self, value: bool) -> None:
        """Set this node's selected state and propagate to all descendants."""
        self.selected = value
        for child in self.children:
            child.set_selected(value)

    def collect_selected_card_ids(self) -> list[int]:
        """Return card_ids from all selected leaf nodes in this subtree.

        If this node has no children it is a leaf: return own _card_ids when
        selected, otherwise [].  If it has children, recurse and aggregate.
        """
        if not self.children:
            return list(self._card_ids) if self.selected else []
        result: list[int] = []
        for child in self.children:
            result.extend(child.collect_selected_card_ids())
        return result


# ---------------------------------------------------------------------------
# Tree builder
# ---------------------------------------------------------------------------

def _get_reading_title(
    conn: sqlite3.Connection,
    deck: str,
    topic_id: str,
) -> str | None:
    """Try to derive a reading title from section_title for a given topic."""
    row = conn.execute(
        "SELECT section_title FROM generation_cards "
        "WHERE deck = ? AND topic_id = ? AND section_title IS NOT NULL "
        "LIMIT 1",
        (deck, topic_id),
    ).fetchone()
    if row and row[0]:
        return row[0]
    return None


def build_tree(
    conn: sqlite3.Connection,
    deck: str | None = None,
) -> list[CatalogNode]:
    """Build the catalog tree from the database.

    Tree hierarchy: deck → topic → source → section

    Special rule for "los" source: if every section under the source has
    exactly 1 card (count == 1), the source node is a leaf (no section
    children shown).  Otherwise, sections appear as children of the source.

    Card counts propagate upward: source.card_count = sum of sections,
    topic.card_count = sum of sources, deck.card_count = sum of topics.

    Parameters
    ----------
    conn:
        Open SQLite connection initialised with init_generation_db.
    deck:
        Optional deck filter.  When provided only cards from that deck are
        included in the tree.

    Returns
    -------
    list[CatalogNode]
        One CatalogNode per deck at the root level.
    """
    # ------------------------------------------------------------------
    # 1. Fetch aggregated counts
    # ------------------------------------------------------------------
    catalog_rows = _fetch_catalog_rows(conn, deck)

    # ------------------------------------------------------------------
    # 2. Fetch card_id mapping for leaf-level nodes
    # ------------------------------------------------------------------
    card_id_map = _fetch_card_id_map(conn, deck)

    # ------------------------------------------------------------------
    # 3. Assemble the tree
    # ------------------------------------------------------------------
    # Structure: deck_nodes[deck_name] -> DeckNode
    #            topic_nodes[(deck, topic_id)] -> TopicNode
    #            source_nodes[(deck, topic_id, source)] -> SourceNode

    deck_nodes: dict[str, CatalogNode] = {}
    topic_nodes: dict[tuple[str, str], CatalogNode] = {}
    source_nodes: dict[tuple[str, str, str], CatalogNode] = {}

    # Group rows by (deck, topic_id, source) to check the LOS leaf rule
    source_sections: dict[tuple[str, str, str], list[dict]] = {}
    for row in catalog_rows:
        key = (row["deck"], row["topic_id"], row["source"])
        source_sections.setdefault(key, []).append(row)

    def _topic_sort_key(key):
        """Sort topics numerically: (deck, topic_id_int, source)."""
        deck_name, topic_id, source = key
        try:
            tid = int(topic_id)
        except ValueError:
            tid = 0
        return (deck_name, tid, source)

    for (deck_name, topic_id, source), sections in sorted(
        source_sections.items(), key=lambda kv: _topic_sort_key(kv[0])
    ):
        # --- Deck node ---
        if deck_name not in deck_nodes:
            deck_nodes[deck_name] = CatalogNode(
                label=deck_name,
                node_type="deck",
                deck=deck_name,
            )

        # --- Topic node ---
        topic_key = (deck_name, topic_id)
        if topic_key not in topic_nodes:
            # Use "Reading N" for numeric topic_ids (CFA LOS), plain name otherwise
            label = f"Reading {topic_id}" if topic_id.isdigit() else topic_id
            topic_node = CatalogNode(
                label=label,
                node_type="topic",
                deck=deck_name,
                topic_id=topic_id,
            )
            topic_nodes[topic_key] = topic_node
            deck_nodes[deck_name].children.append(topic_node)

        # --- Source node ---
        source_key = (deck_name, topic_id, source)
        total_source_cards = sum(s["card_count"] for s in sections)

        source_node = CatalogNode(
            label=source,
            node_type="source",
            card_count=total_source_cards,
            deck=deck_name,
            topic_id=topic_id,
            source=source,
        )
        source_nodes[source_key] = source_node
        topic_nodes[topic_key].children.append(source_node)

        # --- Determine whether to add section children ---
        is_los = source == "los"
        all_single_card = all(s["card_count"] == 1 for s in sections)
        make_leaf = is_los and all_single_card

        if make_leaf:
            # Source node is a leaf: collect all card_ids from its sections
            for s in sections:
                ids = card_id_map.get(
                    (deck_name, topic_id, source, s["section_id"]), []
                )
                source_node._card_ids.extend(ids)
        else:
            # Add section children
            for s in sections:
                section_card_ids = card_id_map.get(
                    (deck_name, topic_id, source, s["section_id"]), []
                )
                section_node = CatalogNode(
                    label=s["section_title"] or s["section_id"],
                    node_type="section",
                    card_count=s["card_count"],
                    deck=deck_name,
                    topic_id=topic_id,
                    source=source,
                    section_id=s["section_id"],
                    section_title=s["section_title"],
                    _card_ids=section_card_ids,
                )
                source_node.children.append(section_node)

    # ------------------------------------------------------------------
    # 4. Propagate card counts upward
    # ------------------------------------------------------------------
    for topic_key, topic_node in topic_nodes.items():
        topic_node.card_count = sum(s.card_count for s in topic_node.children)

    for deck_name, deck_node in deck_nodes.items():
        deck_node.card_count = sum(t.card_count for t in deck_node.children)
        # Sort topics alphabetically within each deck
        deck_node.children.sort(key=lambda n: n.label.lower())

    return list(deck_nodes.values())


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _fetch_catalog_rows(
    conn: sqlite3.Connection,
    deck: str | None,
) -> list[dict]:
    """Wrapper around get_catalog_tree that returns list[dict]."""
    from knowledge_base.srs.generation_db import get_catalog_tree
    return get_catalog_tree(conn, deck=deck)


def _fetch_card_id_map(
    conn: sqlite3.Connection,
    deck: str | None,
) -> dict[tuple[str, str, str, str], list[int]]:
    """Return a mapping of (deck, topic_id, source, section_id) → [card_id, ...]."""
    params: list = []
    where = ""
    if deck is not None:
        where = "WHERE deck = ?"
        params.append(deck)

    sql = (
        "SELECT card_id, deck, topic_id, source, section_id "
        f"FROM generation_cards {where} "
        "ORDER BY deck, topic_id, source, section_id, card_index"
    )
    rows = conn.execute(sql, params).fetchall()

    result: dict[tuple[str, str, str, str], list[int]] = {}
    for row in rows:
        key = (row[1], row[2], row[3], row[4])  # deck, topic_id, source, section_id
        result.setdefault(key, []).append(row[0])
    return result


# ---------------------------------------------------------------------------
# CatalogScreen — Textual TUI Screen
# ---------------------------------------------------------------------------

_CATALOG_CSS = """
#selection-count {
    dock: bottom;
    width: 100%;
    height: 1;
    padding: 0 2;
    color: $text-muted;
}
"""


class CatalogScreen(Screen):
    """Browsable catalog of generation card material."""

    CSS = _CATALOG_CSS

    BINDINGS = [
        Binding("m", "launch_massed", "Massed Practice"),
        Binding("o", "launch_ordered", "Ordered Practice"),
        Binding("q", "quit_catalog", "Quit"),
        Binding("space", "toggle_select", "Select", show=False, priority=True),
    ]

    def __init__(
        self,
        conn: sqlite3.Connection,
        deck: str | None = None,
    ) -> None:
        super().__init__()
        self.conn = conn
        self.deck_filter = deck
        self._catalog_nodes: list[CatalogNode] = []
        # Map from tree-node id to CatalogNode for fast lookup
        self._node_map: dict[int, CatalogNode] = {}

    def compose(self) -> ComposeResult:
        yield Header()
        yield Tree("Generation Card Catalog")
        yield Static("0 cards selected", id="selection-count")
        yield Footer()

    def on_mount(self) -> None:
        self._catalog_nodes = build_tree(self.conn, deck=self.deck_filter)
        tree = self.query_one(Tree)
        tree.root.expand()
        for deck_node in self._catalog_nodes:
            self._add_node_to_tree(tree.root, deck_node)

    def _add_node_to_tree(self, parent_tree_node, catalog_node: CatalogNode) -> None:
        """Recursively add a CatalogNode and its children to the Textual tree."""
        label = self._node_label(catalog_node)
        if catalog_node.children:
            tree_node = parent_tree_node.add(label, data=catalog_node)
        else:
            tree_node = parent_tree_node.add_leaf(label, data=catalog_node)
        self._node_map[tree_node.id] = catalog_node
        for child in catalog_node.children:
            self._add_node_to_tree(tree_node, child)

    @staticmethod
    def _node_label(node: CatalogNode) -> Text:
        """Build the display label with selection marker and card count."""
        if node.selected:
            return Text(f"* {node.label} ({node.card_count})", style="bold")
        return Text(f"  {node.label} ({node.card_count})")

    def _update_tree_labels(self) -> None:
        """Refresh all tree node labels to reflect current selection state."""
        tree = self.query_one(Tree)

        def _walk(node):
            if node.data is not None:
                node.set_label(self._node_label(node.data))
            for child in node.children:
                _walk(child)

        _walk(tree.root)

    def _update_selection_count(self) -> None:
        """Update the selection count display."""
        total = 0
        for deck_node in self._catalog_nodes:
            total += len(deck_node.collect_selected_card_ids())
        label = self.query_one("#selection-count", Static)
        label.update(f"{total} card{'s' if total != 1 else ''} selected")

    def action_toggle_select(self) -> None:
        """Toggle selection on the node under cursor, cascading to children."""
        tree = self.query_one(Tree)
        cursor_node = tree.cursor_node
        if cursor_node is None or cursor_node.data is None:
            return
        catalog_node: CatalogNode = cursor_node.data
        catalog_node.set_selected(not catalog_node.selected)
        self._update_tree_labels()
        self._update_selection_count()

    def _collect_all_selected_ids(self) -> list[int]:
        """Gather card IDs from all selected nodes across all deck roots."""
        ids: list[int] = []
        for deck_node in self._catalog_nodes:
            ids.extend(deck_node.collect_selected_card_ids())
        return ids

    def action_launch_massed(self) -> None:
        """Dismiss screen with massed practice mode and selected card IDs."""
        card_ids = self._collect_all_selected_ids()
        if not card_ids:
            return
        self.dismiss(("massed", card_ids))

    def action_launch_ordered(self) -> None:
        """Dismiss screen with ordered practice mode and selected card IDs."""
        card_ids = self._collect_all_selected_ids()
        if not card_ids:
            return
        self.dismiss(("ordered", card_ids))

    def action_quit_catalog(self) -> None:
        """Exit the application from the catalog screen."""
        self.app.exit()
