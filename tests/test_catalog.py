"""Tests for srs/catalog.py — CatalogNode and build_tree."""

import pytest

from knowledge_base.srs.catalog import CatalogNode, build_tree
from knowledge_base.srs.generation_db import init_generation_db, insert_generation_card


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def conn():
    """In-memory DB initialised with generation schema."""
    return init_generation_db()


def _card(deck="cfa_level1", source="los", topic_id="1",
          section_id="1.a", section_title="Intro", card_index=0,
          question="Q?", answer="A.") -> dict:
    return {
        "deck": deck,
        "source": source,
        "topic_id": topic_id,
        "section_id": section_id,
        "section_title": section_title,
        "card_index": card_index,
        "question": question,
        "answer": answer,
        "tags": "[]",
    }


# ---------------------------------------------------------------------------
# CatalogNode unit tests
# ---------------------------------------------------------------------------

class TestCatalogNodeSelectPropagation:
    def test_set_selected_true_propagates_to_children(self):
        child1 = CatalogNode(label="c1", node_type="section")
        child2 = CatalogNode(label="c2", node_type="section")
        parent = CatalogNode(label="p", node_type="source", children=[child1, child2])

        parent.set_selected(True)

        assert parent.selected is True
        assert child1.selected is True
        assert child2.selected is True

    def test_set_selected_false_propagates_to_children(self):
        child = CatalogNode(label="c", node_type="section", selected=True)
        parent = CatalogNode(label="p", node_type="source", selected=True, children=[child])

        parent.set_selected(False)

        assert parent.selected is False
        assert child.selected is False

    def test_set_selected_propagates_deeply(self):
        leaf = CatalogNode(label="leaf", node_type="section")
        mid = CatalogNode(label="mid", node_type="source", children=[leaf])
        root = CatalogNode(label="root", node_type="deck", children=[mid])

        root.set_selected(True)

        assert root.selected is True
        assert mid.selected is True
        assert leaf.selected is True


class TestCatalogNodeCollectCardIds:
    def test_leaf_selected_returns_card_ids(self):
        node = CatalogNode(label="s", node_type="section", selected=True, _card_ids=[1, 2, 3])
        assert node.collect_selected_card_ids() == [1, 2, 3]

    def test_leaf_not_selected_returns_empty(self):
        node = CatalogNode(label="s", node_type="section", selected=False, _card_ids=[1, 2])
        assert node.collect_selected_card_ids() == []

    def test_parent_collects_from_selected_children(self):
        c1 = CatalogNode(label="c1", node_type="section", selected=True, _card_ids=[10, 11])
        c2 = CatalogNode(label="c2", node_type="section", selected=False, _card_ids=[20])
        parent = CatalogNode(label="p", node_type="source", children=[c1, c2])

        result = parent.collect_selected_card_ids()
        assert sorted(result) == [10, 11]

    def test_parent_collects_from_all_selected_children(self):
        c1 = CatalogNode(label="c1", node_type="section", selected=True, _card_ids=[1])
        c2 = CatalogNode(label="c2", node_type="section", selected=True, _card_ids=[2])
        parent = CatalogNode(label="p", node_type="source", children=[c1, c2])
        parent.set_selected(True)

        result = parent.collect_selected_card_ids()
        assert sorted(result) == [1, 2]

    def test_select_then_collect_returns_all_leaf_ids(self):
        leaf1 = CatalogNode(label="l1", node_type="section", _card_ids=[100])
        leaf2 = CatalogNode(label="l2", node_type="section", _card_ids=[200])
        source = CatalogNode(label="s", node_type="source", children=[leaf1, leaf2])
        root = CatalogNode(label="r", node_type="deck", children=[source])

        root.set_selected(True)
        result = root.collect_selected_card_ids()
        assert sorted(result) == [100, 200]


# ---------------------------------------------------------------------------
# build_tree integration tests
# ---------------------------------------------------------------------------

class TestBuildTreeStructure:
    def test_deck_at_root(self, conn):
        insert_generation_card(conn, _card(deck="cfa_level1", topic_id="1",
                                           section_id="1.a", card_index=0))
        trees = build_tree(conn)
        assert len(trees) == 1
        assert trees[0].node_type == "deck"
        assert trees[0].label == "cfa_level1"

    def test_topics_under_deck(self, conn):
        insert_generation_card(conn, _card(topic_id="1", section_id="1.a", card_index=0))
        insert_generation_card(conn, _card(topic_id="2", section_id="2.a", card_index=0))
        trees = build_tree(conn)
        deck_node = trees[0]
        topic_ids = {t.topic_id for t in deck_node.children}
        assert "1" in topic_ids
        assert "2" in topic_ids
        assert all(t.node_type == "topic" for t in deck_node.children)

    def test_sources_under_topic(self, conn):
        insert_generation_card(conn, _card(topic_id="1", source="los",
                                           section_id="1.a", card_index=0))
        insert_generation_card(conn, _card(topic_id="1", source="markdown",
                                           section_id="note1", card_index=0))
        trees = build_tree(conn)
        deck_node = trees[0]
        topic_node = next(t for t in deck_node.children if t.topic_id == "1")
        source_labels = {s.label for s in topic_node.children}
        assert "los" in source_labels
        assert "markdown" in source_labels
        assert all(s.node_type == "source" for s in topic_node.children)

    def test_sections_under_multi_card_source(self, conn):
        # Two cards in the same section_id of a non-los source → sections shown
        insert_generation_card(conn, _card(topic_id="1", source="markdown",
                                           section_id="note1",
                                           section_title="Note One",
                                           card_index=0))
        insert_generation_card(conn, _card(topic_id="1", source="markdown",
                                           section_id="note1",
                                           section_title="Note One",
                                           card_index=1))
        trees = build_tree(conn)
        deck = trees[0]
        topic = next(t for t in deck.children if t.topic_id == "1")
        source = next(s for s in topic.children if s.source == "markdown")
        assert len(source.children) == 1  # one section_id
        assert source.children[0].node_type == "section"
        assert source.children[0].section_id == "note1"


class TestBuildTreeLosLeafRule:
    def test_los_source_is_leaf_when_all_sections_have_one_card(self, conn):
        """LOS source with all single-card sections should be a leaf node."""
        insert_generation_card(conn, _card(topic_id="1", source="los",
                                           section_id="1.a", card_index=0))
        insert_generation_card(conn, _card(topic_id="1", source="los",
                                           section_id="1.b", card_index=0))
        trees = build_tree(conn)
        deck = trees[0]
        topic = next(t for t in deck.children if t.topic_id == "1")
        los_source = next(s for s in topic.children if s.source == "los")
        # Leaf rule: no section children
        assert los_source.children == []

    def test_los_source_has_section_children_when_section_has_multiple_cards(self, conn):
        """LOS source with a section having >1 card should show section children."""
        insert_generation_card(conn, _card(topic_id="1", source="los",
                                           section_id="1.a", card_index=0))
        insert_generation_card(conn, _card(topic_id="1", source="los",
                                           section_id="1.a", card_index=1))
        trees = build_tree(conn)
        deck = trees[0]
        topic = next(t for t in deck.children if t.topic_id == "1")
        los_source = next(s for s in topic.children if s.source == "los")
        assert len(los_source.children) == 1
        assert los_source.children[0].section_id == "1.a"

    def test_non_los_source_always_shows_sections(self, conn):
        """Non-LOS sources always show section children, even with 1 card."""
        insert_generation_card(conn, _card(topic_id="1", source="markdown",
                                           section_id="note1", card_index=0))
        trees = build_tree(conn)
        deck = trees[0]
        topic = next(t for t in deck.children if t.topic_id == "1")
        md_source = next(s for s in topic.children if s.source == "markdown")
        assert len(md_source.children) == 1
        assert md_source.children[0].section_id == "note1"


class TestBuildTreeCardCountPropagation:
    def test_section_card_count(self, conn):
        insert_generation_card(conn, _card(topic_id="1", source="markdown",
                                           section_id="note1", card_index=0))
        insert_generation_card(conn, _card(topic_id="1", source="markdown",
                                           section_id="note1", card_index=1))
        trees = build_tree(conn)
        deck = trees[0]
        topic = next(t for t in deck.children if t.topic_id == "1")
        source = next(s for s in topic.children if s.source == "markdown")
        section = source.children[0]
        assert section.card_count == 2

    def test_source_card_count_sums_sections(self, conn):
        insert_generation_card(conn, _card(topic_id="1", source="markdown",
                                           section_id="note1", card_index=0))
        insert_generation_card(conn, _card(topic_id="1", source="markdown",
                                           section_id="note2", card_index=0))
        trees = build_tree(conn)
        deck = trees[0]
        topic = next(t for t in deck.children if t.topic_id == "1")
        source = next(s for s in topic.children if s.source == "markdown")
        assert source.card_count == 2

    def test_topic_card_count_sums_sources(self, conn):
        insert_generation_card(conn, _card(topic_id="1", source="los",
                                           section_id="1.a", card_index=0))
        insert_generation_card(conn, _card(topic_id="1", source="markdown",
                                           section_id="note1", card_index=0))
        insert_generation_card(conn, _card(topic_id="1", source="markdown",
                                           section_id="note1", card_index=1))
        trees = build_tree(conn)
        deck = trees[0]
        topic = next(t for t in deck.children if t.topic_id == "1")
        assert topic.card_count == 3

    def test_deck_card_count_sums_topics(self, conn):
        insert_generation_card(conn, _card(topic_id="1", source="los",
                                           section_id="1.a", card_index=0))
        insert_generation_card(conn, _card(topic_id="2", source="los",
                                           section_id="2.a", card_index=0))
        trees = build_tree(conn)
        deck = trees[0]
        assert deck.card_count == 2


class TestBuildTreeCardIdMapping:
    def test_los_leaf_node_has_card_ids(self, conn):
        id1 = insert_generation_card(conn, _card(topic_id="1", source="los",
                                                  section_id="1.a", card_index=0))
        id2 = insert_generation_card(conn, _card(topic_id="1", source="los",
                                                  section_id="1.b", card_index=0))
        trees = build_tree(conn)
        deck = trees[0]
        topic = next(t for t in deck.children if t.topic_id == "1")
        los_source = next(s for s in topic.children if s.source == "los")
        # LOS leaf rule: card_ids collected at source level
        assert sorted(los_source._card_ids) == sorted([id1, id2])

    def test_section_leaf_has_card_ids(self, conn):
        id1 = insert_generation_card(conn, _card(topic_id="1", source="markdown",
                                                   section_id="note1", card_index=0))
        id2 = insert_generation_card(conn, _card(topic_id="1", source="markdown",
                                                   section_id="note1", card_index=1))
        trees = build_tree(conn)
        deck = trees[0]
        topic = next(t for t in deck.children if t.topic_id == "1")
        source = next(s for s in topic.children if s.source == "markdown")
        section = source.children[0]
        assert sorted(section._card_ids) == sorted([id1, id2])

    def test_collect_selected_card_ids_after_build(self, conn):
        id1 = insert_generation_card(conn, _card(topic_id="1", source="los",
                                                   section_id="1.a", card_index=0))
        id2 = insert_generation_card(conn, _card(topic_id="1", source="los",
                                                   section_id="1.b", card_index=0))
        trees = build_tree(conn)
        deck = trees[0]
        deck.set_selected(True)
        result = deck.collect_selected_card_ids()
        assert sorted(result) == sorted([id1, id2])


class TestBuildTreeDeckFilter:
    def test_deck_filter_returns_only_matching_deck(self, conn):
        insert_generation_card(conn, _card(deck="cfa_level1", topic_id="1",
                                           source="los", section_id="1.a",
                                           card_index=0))
        insert_generation_card(conn, _card(deck="other_deck", topic_id="1",
                                           source="los", section_id="1.a",
                                           card_index=0))
        trees = build_tree(conn, deck="cfa_level1")
        assert len(trees) == 1
        assert trees[0].label == "cfa_level1"

    def test_no_filter_returns_all_decks(self, conn):
        insert_generation_card(conn, _card(deck="deck_a", topic_id="1",
                                           source="los", section_id="1.a",
                                           card_index=0))
        insert_generation_card(conn, _card(deck="deck_b", topic_id="1",
                                           source="los", section_id="1.a",
                                           card_index=0))
        trees = build_tree(conn)
        deck_names = {t.label for t in trees}
        assert "deck_a" in deck_names
        assert "deck_b" in deck_names
