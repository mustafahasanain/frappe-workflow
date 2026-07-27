"""Unit tests for scripts/core/feature_registry.py."""

import unittest

import support
from core import feature_registry


class ParsingTests(unittest.TestCase):
    def setUp(self):
        self.text = support.read_fixture("sample-feature-changelog.md")

    def test_parse_index(self):
        rows = feature_registry.parse_index(self.text)
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0].feature_id, "FEAT-STOCK-001")
        self.assertEqual(rows[1].module, "Purchase")
        self.assertEqual(rows[2].type, "Integration")

    def test_parse_entries(self):
        entries = feature_registry.parse_entries(self.text)
        ids = [e.feature_id for e in entries]
        self.assertEqual(
            ids, ["FEAT-STOCK-001", "CHANGE-PURCHASE-001", "INT-TELEGRAM-001"]
        )
        stock = entries[0]
        self.assertEqual(stock.fields["Status"], "Active")
        self.assertEqual(stock.fields["Module"], "Stock")


class NextIdTests(unittest.TestCase):
    def setUp(self):
        self.text = support.read_fixture("sample-feature-changelog.md")

    def test_next_id_same_module(self):
        self.assertEqual(
            feature_registry.next_feature_id(self.text, "FEATURE", "Stock"),
            "FEAT-STOCK-002",
        )

    def test_next_id_new_module(self):
        self.assertEqual(
            feature_registry.next_feature_id(self.text, "BUGFIX", "Selling"),
            "BUG-SELLING-001",
        )

    def test_module_token_normalization(self):
        self.assertEqual(
            feature_registry.next_feature_id(self.text, "FEATURE", "Sales Invoice"),
            "FEAT-SALES_INVOICE-001",
        )

    def test_sequence_preserved_per_type_and_module(self):
        text = self.text + "\n## [FEATURE] Another Stock Thing\n\n- **ID:** FEAT-STOCK-007\n"
        self.assertEqual(
            feature_registry.next_feature_id(text, "FEATURE", "Stock"),
            "FEAT-STOCK-008",
        )
        # a different type in the same module keeps its own sequence
        self.assertEqual(
            feature_registry.next_feature_id(text, "CHANGE", "Stock"),
            "CHANGE-STOCK-001",
        )

    def test_unknown_type_rejected(self):
        with self.assertRaises(feature_registry.RegistryError):
            feature_registry.next_feature_id(self.text, "EPIC", "Stock")


class SearchTests(unittest.TestCase):
    def setUp(self):
        self.text = support.read_fixture("sample-feature-changelog.md")

    def test_search_finds_reservation(self):
        results = feature_registry.search(self.text, "stock reservation")
        self.assertTrue(results)
        self.assertEqual(results[0]["id"], "FEAT-STOCK-001")
        self.assertGreaterEqual(results[0]["score"], 60)

    def test_search_no_match(self):
        results = feature_registry.search(self.text, "warehouse barcode scanning")
        top_ids = [r["id"] for r in results if r["score"] >= 60]
        self.assertEqual(top_ids, [])

    def test_search_empty_query(self):
        self.assertEqual(feature_registry.search(self.text, "   "), [])


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.text = support.read_fixture("sample-feature-changelog.md")

    def test_valid_registry_passes(self):
        self.assertEqual(feature_registry.validate_registry(self.text), [])

    def test_duplicate_index_id_detected(self):
        dup = self.text.replace(
            "| CHANGE-PURCHASE-001 | Change |",
            "| FEAT-STOCK-001 | Change |",
            1,
        )
        errors = feature_registry.validate_registry(dup)
        self.assertTrue(any("REG_DUP_INDEX_ID" in e for e in errors))

    def test_index_without_entry_detected(self):
        extra = self.text.replace(
            "| INT-TELEGRAM-001 | Integration | Telegram Reports | Telegram | Active | telegram, bot, reporting |",
            "| INT-TELEGRAM-001 | Integration | Telegram Reports | Telegram | Active | telegram, bot, reporting |\n"
            "| FEAT-STOCK-009 | Feature | Ghost Feature | Stock | Active | ghost |",
        )
        errors = feature_registry.validate_registry(extra)
        self.assertTrue(any("REG_NO_ENTRY" in e and "FEAT-STOCK-009" in e for e in errors))

    def test_entry_without_index_detected(self):
        extra = self.text + (
            "\n## [FEATURE] Orphan Entry\n\n"
            "- **ID:** FEAT-STOCK-042\n"
            "- **Status:** Active\n"
            "- **Module:** Stock\n"
        )
        errors = feature_registry.validate_registry(extra)
        self.assertTrue(any("REG_NOT_IN_INDEX" in e for e in errors))

    def test_status_mismatch_detected(self):
        broken = self.text.replace(
            "- **ID:** CHANGE-PURCHASE-001\n- **Status:** Active",
            "- **ID:** CHANGE-PURCHASE-001\n- **Status:** Deprecated",
        )
        errors = feature_registry.validate_registry(broken)
        self.assertTrue(any("REG_STATUS_MISMATCH" in e for e in errors))

    def test_invalid_status_value_detected(self):
        broken = self.text.replace(
            "| FEAT-STOCK-001 | Feature | Temporary Stock Reservation | Stock | Active |",
            "| FEAT-STOCK-001 | Feature | Temporary Stock Reservation | Stock | Completed |",
        ).replace(
            "- **ID:** FEAT-STOCK-001\n- **Status:** Active",
            "- **ID:** FEAT-STOCK-001\n- **Status:** Completed",
        )
        errors = feature_registry.validate_registry(broken)
        self.assertTrue(any("REG_STATUS" in e for e in errors))

    def test_replacement_link_must_exist(self):
        broken = self.text.replace(
            "- **ID:** FEAT-STOCK-001\n- **Status:** Active",
            "- **ID:** FEAT-STOCK-001\n- **Status:** Replaced\n- **Replaced By:** FEAT-STOCK-777",
        ).replace(
            "| FEAT-STOCK-001 | Feature | Temporary Stock Reservation | Stock | Active |",
            "| FEAT-STOCK-001 | Feature | Temporary Stock Reservation | Stock | Replaced |",
        )
        errors = feature_registry.validate_registry(broken)
        self.assertTrue(any("REG_REPLACED_BY_MISSING" in e for e in errors))

    def test_replaced_without_link_detected(self):
        broken = self.text.replace(
            "- **ID:** FEAT-STOCK-001\n- **Status:** Active",
            "- **ID:** FEAT-STOCK-001\n- **Status:** Replaced",
        ).replace(
            "| FEAT-STOCK-001 | Feature | Temporary Stock Reservation | Stock | Active |",
            "| FEAT-STOCK-001 | Feature | Temporary Stock Reservation | Stock | Replaced |",
        )
        errors = feature_registry.validate_registry(broken)
        self.assertTrue(any("REG_REPLACED_NO_LINK" in e for e in errors))

    def test_prefix_type_mismatch_detected(self):
        broken = self.text.replace(
            "| CHANGE-PURCHASE-001 | Change |",
            "| CHANGE-PURCHASE-001 | Feature |",
        ).replace("## [CHANGE] Purchase Unit Price Calculation", "## [FEATURE] Purchase Unit Price Calculation")
        errors = feature_registry.validate_registry(broken)
        self.assertTrue(any("REG_PREFIX_TYPE" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
