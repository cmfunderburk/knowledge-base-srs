"""Catalog tree builder and selection logic for the generation card TUI.

Provides CatalogNode (a tree node with selection and card-ID collection) and
build_tree (constructs the deck → topic → source → section hierarchy from the
database).
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field


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

    for (deck_name, topic_id, source), sections in source_sections.items():
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
            # Try to get a descriptive label
            title = _get_reading_title(conn, deck_name, topic_id)
            label = title if title else f"Reading {topic_id}"
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
