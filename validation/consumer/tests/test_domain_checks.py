"""Actual native gates: acceptance, peer agreement with wrong values, bad input."""
from pathlib import Path
import tempfile
import unittest

from equiframe_consumer_lab.domain_checks import DOMAINS, declarations, run_domain_case
from equiframe_consumer_lab.evidence import ConsumerError


class DomainChecks(unittest.TestCase):
    def test_three_domains_preserve_negative_meaning_and_publication(self):
        for domain in DOMAINS:
            for variant, expected in (("good", 0), ("different", 1), ("invalid", 2)):
                with self.subTest(domain=domain, variant=variant), tempfile.TemporaryDirectory() as directory:
                    row = run_domain_case(Path(directory)/"case", domain, variant, "pandas", "duckdb")
                    self.assertEqual(row["observed_exit_code"], expected)
                    self.assertEqual(row["published"], variant == "good")
                    self.assertEqual(row["native_execution_count"], 0 if variant == "invalid" else 2)
                    self.assertEqual(row["comparison_max_rows"], 100)
                    self.assertEqual(row["fixture_rows"], 2)

    def test_invalid_domain_or_variant_is_not_an_input_rejection(self):
        with self.assertRaises(ValueError): declarations("unknown", "good")
        with self.assertRaises(ValueError): declarations("finance", "unknown")

    def test_bad_direction_does_not_produce_a_success_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/"case"
            with self.assertRaises(ConsumerError): run_domain_case(output, "finance", "good", "pandas", "pandas")
            self.assertFalse(output.exists())
