"""Synthetic unit fixtures for the handoff tooling, never observations from the VM."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path, PurePosixPath
from unittest.mock import patch

from assemble_kit import candidate_scope
from check_benchmark_profile import requirements, resolution_command
from check_upgrade_rollback import DOCUMENTARY_A7_CORE_HASH, OLD_HASHES
from manifest_scope import (
    receipt_schema,
    required_pythons,
    requires_runtime_identity,
    validate_cell_scope,
)
from measure_maturity import observed_filesystem
from run_vm_lab import Recorder, python_at, sha, verify_kit, write_runtime_constraints
from validate_vm_receipts import Review, member


class HandoffToolsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def file(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def review(self):
        review = Review.__new__(Review)
        review.test_manifests = {}
        review.evidence = self.root
        review.inventory = {
            p.relative_to(self.root).as_posix(): {
                "sha256": sha(p),
                "size_bytes": p.stat().st_size,
            }
            for p in self.root.rglob("*")
            if p.is_file()
        }
        return review

    def test_separate_original_m13_expedition_preserves_all_receipt_cells(self):
        candidate = candidate_scope("original-m13-arm")
        self.assertEqual(required_pythons(candidate), ("3.10", "3.12"))
        self.assertFalse(candidate["universality_matrix_reduced"])
        self.assertFalse(candidate["other_platforms_and_python_minors_closed"])
        self.assertEqual(candidate["criteria_automatically_closed"], [])
        self.assertTrue(requires_runtime_identity(candidate))
        for wrong in (None, False):
            with self.subTest(marker=wrong), self.assertRaises(ValueError):
                required_pythons({**candidate, "required_runtime_identity": wrong})
        with self.assertRaises(ValueError):
            validate_cell_scope(
                candidate,
                {
                    "schema": "equiframe-maturity-vm-execution-1",
                    "python_cells": [{"minor": "3.12"}],
                },
            )

    def test_universality_scope_still_rejects_a_two_minor_receipt(self):
        candidate = candidate_scope("universality")
        self.assertEqual(required_pythons(candidate), ("3.10", "3.11", "3.12", "3.13"))
        with self.assertRaises(ValueError):
            validate_cell_scope(
                candidate,
                {
                    "schema": "equiframe-maturity-vm-execution-2",
                    "required_python_versions": ["3.10", "3.11", "3.12", "3.13"],
                    "python_cells": [{"minor": "3.10"}, {"minor": "3.12"}],
                },
            )

    def test_scope_is_explicit_and_returns_independent_manifests(self):
        with self.assertRaises(ValueError):
            candidate_scope("infer-from-installed-python")
        mutated = candidate_scope("universality")
        mutated["required_python_versions"].pop()
        self.assertEqual(
            len(candidate_scope("universality")["required_python_versions"]), 4
        )

    def test_upgrade_uses_reviewed_executable_a7_identity(self):
        self.assertEqual(
            OLD_HASHES["core"],
            "5d435e75a79754ab45c8a27f7d30ff513c006034bdddbff170ec9506816b9ff0",
        )
        self.assertEqual(
            DOCUMENTARY_A7_CORE_HASH,
            "abab950c4bdbaf38056f493ca4efc97148b0d85d8d34322d2725437c9f2b42c9",
        )
        self.assertNotEqual(OLD_HASHES["core"], DOCUMENTARY_A7_CORE_HASH)

    def test_python_at_supports_windows_and_posix_venv_layouts(self):
        windows = self.file("windows/Scripts/python.exe", "synthetic")
        posix = self.file("posix/bin/python", "synthetic")
        self.assertEqual(python_at(self.root / "windows"), str(windows))
        self.assertEqual(python_at(self.root / "posix"), str(posix))
        with self.assertRaises(FileNotFoundError):
            python_at(self.root / "missing")

    @unittest.skipUnless(
        os.name == "posix", "POSIX virtual environments use interpreter links"
    )
    def test_python_at_preserves_a_valid_posix_interpreter_link(self):
        entry = self.root / "linked/bin/python"
        entry.parent.mkdir(parents=True)
        entry.symlink_to(sys.executable)
        self.assertEqual(python_at(self.root / "linked"), str(entry))
        entry.unlink()
        entry.symlink_to(self.root / "missing-interpreter")
        with self.assertRaises(FileNotFoundError):
            python_at(self.root / "linked")

    def test_member_rejects_traversal_even_when_target_exists(self):
        self.file("nested/value", "synthetic")
        with self.assertRaises(ValueError):
            member(self.root, "nested/../nested/value")

    def test_member_rejects_absolute_member(self):
        path = self.file("value", "synthetic")
        with self.assertRaises(ValueError):
            member(self.root, str(path))

    def test_linux_receipt_paths_are_relative_on_every_review_host(self):
        review = self.review()
        review.lab = PurePosixPath("/home/hernan/owned-lab")
        self.assertEqual(
            review.relative("/home/hernan/owned-lab/py3.10-all/receipt.json"),
            "py3.10-all/receipt.json",
        )
        self.assertEqual(
            review.relative("py3.10-all/receipt.json"), "py3.10-all/receipt.json"
        )
        with self.assertRaises(ValueError):
            review.relative("/home/hernan/other-lab/receipt.json")
        for invalid in ("../outside", "nested/../receipt.json", "nested\\receipt.json"):
            with (
                self.subTest(invalid=invalid),
                self.assertRaisesRegex(ValueError, "canonical"),
            ):
                review.relative(invalid)

    def test_member_accepts_inventory_file(self):
        path = self.file("value", "synthetic")
        self.assertEqual(member(self.root, "value"), path)

    def test_required_file_must_be_in_inventory(self):
        self.file("value", "synthetic")
        review = self.review()
        self.file("late-file", "unrecorded")
        with self.assertRaisesRegex(ValueError, "not inventoried"):
            review.file("late-file")

    def test_inventory_detects_changed_bytes(self):
        path = self.file("value", "original")
        review = self.review()
        path.write_text("changed")
        with self.assertRaisesRegex(ValueError, "differs"):
            review.file("value")

    def test_independent_receipt_hash_is_checked(self):
        self.file("value", "original")
        with self.assertRaisesRegex(ValueError, "digest differs"):
            self.review().file("value", "0" * 64)

    def test_absent_commands_do_not_establish_a_pass(self):
        with self.assertRaisesRegex(ValueError, "missing"):
            self.review().commands([], {"install"})

    def test_duplicate_command_labels_do_not_establish_a_pass(self):
        with self.assertRaisesRegex(ValueError, "repeated"):
            self.review().commands(
                [{"label": "install"}, {"label": "install"}], {"install"}
            )

    def test_timeout_cannot_pass_even_with_null_expected_exit(self):
        with self.assertRaisesRegex(ValueError, "timed-out"):
            self.review().commands(
                [
                    {
                        "label": "install",
                        "status": "timeout",
                        "exit_code": None,
                        "expected_exit": None,
                    }
                ],
                {"install"},
            )

    def test_junit_cannot_hide_a_skip(self):
        self.file(
            "suite.xml",
            '<testsuite tests="1"><testcase name="synthetic"><skipped/></testcase></testsuite>',
        )
        with self.assertRaisesRegex(ValueError, "skipped"):
            self.review().junit("suite.xml", 1)

    def test_junit_cannot_hide_missing_cases(self):
        self.file(
            "suite.xml", '<testsuite tests="1"><testcase name="synthetic"/></testsuite>'
        )
        with self.assertRaisesRegex(ValueError, "incomplete"):
            self.review().junit("suite.xml", 2)

    def test_junit_rejects_declared_count_drift(self):
        self.file(
            "suite.xml", '<testsuite tests="2"><testcase name="synthetic"/></testsuite>'
        )
        with self.assertRaisesRegex(ValueError, "count"):
            self.review().junit("suite.xml", 1)

    def test_junit_accepts_complete_synthetic_fixture_without_claiming_vm(self):
        self.file(
            "suite.xml", '<testsuite tests="1"><testcase name="synthetic"/></testsuite>'
        )
        self.review().junit("suite.xml", 1)

    def test_candidate_changed_member_is_rejected(self):
        path = self.file("payload", "initial")
        manifest = {
            "schema": "equiframe-maturity-candidate-1",
            "files": {
                "payload": {"sha256": sha(path), "size_bytes": path.stat().st_size}
            },
        }
        self.file("candidate.json", json.dumps(manifest))
        path.write_text("changed")
        with self.assertRaisesRegex(ValueError, "hash/size"):
            verify_kit(self.root)

    def test_recorder_retains_expected_nonzero(self):
        receipt = {"commands": []}
        record = Recorder(self.root, receipt)
        record.run(
            "synthetic-rejection",
            [sys.executable, "-I", "-c", "raise SystemExit(3)"],
            expected=3,
        )
        self.assertEqual(receipt["commands"][0]["exit_code"], 3)
        self.assertEqual(receipt["commands"][0]["status"], "passed")
        self.assertEqual(
            sha(self.root / receipt["commands"][0]["log"]),
            receipt["commands"][0]["log_sha256"],
        )

    def test_recorder_environment_does_not_forward_credentials(self):
        source = {
            "PATH": os.environ.get("PATH", "test-path"),
            "HOME": "test-home",
            "AWS_ACCESS_KEY_ID": "must-not-leak",
            "AWS_SECRET_ACCESS_KEY": "must-not-leak",
            "GH_PAT": "must-not-leak",
            "SSH_AUTH_SOCK": "must-not-leak",
            "HTTPS_PROXY": "https://credential@example.invalid",
            "PYTHONPATH": "must-not-influence-tests",
        }
        with patch.dict(os.environ, source, clear=True):
            record = Recorder(self.root, {"commands": []})
        self.assertEqual(record.environment["PATH"], source["PATH"])
        self.assertEqual(record.environment["HOME"], "test-home")
        for name in set(source) - {"PATH", "HOME"}:
            self.assertNotIn(name, record.environment)

    def test_consumer_case_requires_the_declared_optimization_mode(self):
        dataset_hash = "a" * 64
        case = {
            "program": "reconciliation",
            "variant": "good",
            "direction": "pandas->duckdb",
            "observed_exit_code": 0,
            "expected_exit_code": 0,
            "status": "PASS",
            "accepted": True,
            "published": True,
            "evidence_integrity_verified": True,
            "portable_verified_without_native_origin": True,
            "frozen_data_unchanged": True,
            "native_execution_count_complete": True,
            "dataset_manifest_sha256": dataset_hash,
            "native_result": {
                "executions": [{"engine": "pandas"}, {"engine": "duckdb"}]
            },
            "environment": {
                "python": "3.12.1",
                "machine": "aarch64",
                "isolated": 1,
                "optimized": 1,
            },
        }
        self.file("case.json", json.dumps(case))
        review = self.review()
        review.candidate = {
            "files": {"consumer-data/manifest.json": {"sha256": dataset_hash}}
        }
        review.consumer_case(
            "case.json",
            "3.12",
            "reconciliation",
            "good",
            "pandas",
            "duckdb",
            optimized=True,
        )
        with self.assertRaisesRegex(ValueError, "optimized execution"):
            review.consumer_case(
                "case.json",
                "3.12",
                "reconciliation",
                "good",
                "pandas",
                "duckdb",
            )

    def test_recorder_retains_unexpected_nonzero(self):
        receipt = {"commands": []}
        record = Recorder(self.root, receipt)
        with self.assertRaises(RuntimeError):
            record.run(
                "synthetic-failure", [sys.executable, "-I", "-c", "raise SystemExit(2)"]
            )
        self.assertEqual(receipt["commands"][0]["status"], "failed")
        self.assertEqual(receipt["commands"][0]["exit_code"], 2)

    def test_recorder_retains_timeout_as_unknown_exit(self):
        receipt = {"commands": []}
        record = Recorder(self.root, receipt)
        with self.assertRaises(subprocess.TimeoutExpired):
            record.run(
                "synthetic-timeout",
                [sys.executable, "-I", "-c", "import time; time.sleep(30)"],
                timeout=0.05,
            )
        self.assertEqual(receipt["commands"][0]["status"], "timeout")
        self.assertIsNone(receipt["commands"][0]["exit_code"])

    def wheel(self, name, metadata):
        path = self.root / (name + ".whl")
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr(name + ".dist-info/METADATA", metadata)
        return path

    def test_benchmark_runtime_markers_follow_actual_target(self):
        core = self.wheel(
            "core",
            "Name: equiframe\nVersion: 0.12.0a8\n"
            'Requires-Dist: pyarrow>=20; extra == "arrow"\n'
            'Requires-Dist: scikit-learn>=1.7; extra == "ml"\n\n',
        )
        benchmark = self.wheel(
            "benchmark",
            "Name: equiframe-benchmark\nVersion: 0.12.0a8\n"
            "Requires-Dist: equiframe[arrow]==0.12.0a8\n"
            'Requires-Dist: equiframe[ml]==0.12.0a8; extra == "ml"\n'
            'Requires-Dist: tomli>=2.2; python_version < "3.11"\n\n',
        )
        self.assertEqual(
            requirements(core, benchmark, "ml", {"python_version": "3.10"}),
            ["pyarrow>=20", "scikit-learn>=1.7", "tomli>=2.2"],
        )
        self.assertEqual(
            requirements(core, benchmark, "base", {"python_version": "3.12"}),
            ["pyarrow>=20"],
        )

    def test_benchmark_resolution_matches_binary_only_installation(self):
        command = resolution_command(
            ["uv", "--no-config", "--cache-dir", "cache"],
            self.root / "runtime.in",
            "/usr/bin/python3.13",
            "minimum",
            self.root / "runtime.lock",
        )
        self.assertIn("--generate-hashes", command)
        self.assertEqual(command.count("--only-binary"), 1)
        binary = command.index("--only-binary")
        self.assertEqual(command[binary + 1], ":all:")
        resolution = command.index("--resolution")
        self.assertEqual(command[resolution + 1], "lowest-direct")

    def test_benchmark_resolution_rejects_unknown_endpoint(self):
        with self.assertRaisesRegex(ValueError, "unknown benchmark profile endpoint"):
            resolution_command(
                ["uv"],
                self.root / "runtime.in",
                sys.executable,
                "oldest",
                self.root / "lock",
            )

    def test_cloud_validation_receipt_is_never_vm_evidence(self):
        review = self.review()
        review.candidate = {}
        review.receipt = {
            "schema": "equiframe-maturity-vm-execution-1",
            "cloud_validation_only": True,
        }
        with self.assertRaisesRegex(ValueError, "not evidence"):
            review.validate()

    def test_different_candidate_receipt_is_rejected(self):
        self.file("candidate.json", "{}")
        review = self.review()
        review.kit = self.root
        review.candidate = {}
        review.receipt = {
            "schema": "equiframe-maturity-vm-execution-1",
            "cloud_validation_only": False,
            "candidate_manifest_sha256": "0" * 64,
        }
        with self.assertRaisesRegex(ValueError, "another candidate"):
            review.validate()

    def test_runtime_constraints_keep_pins_without_implicit_hash_mode(self):
        path = self.root / "constraints.txt"
        write_runtime_constraints(
            path, {"typing-extensions": "4.15.0", "numpy": "2.2.6"}
        )
        self.assertEqual(path.read_text(), "numpy==2.2.6\ntyping-extensions==4.15.0\n")
        self.assertNotIn("--hash", path.read_text())

    def test_runtime_constraints_reject_non_version_input(self):
        with self.assertRaises(ValueError):
            write_runtime_constraints(
                self.root / "constraints", {"numpy": "2.2.6\nother==1"}
            )

    def test_runtime_constraints_reject_empty_resolution(self):
        with self.assertRaises(ValueError):
            write_runtime_constraints(self.root / "constraints", {})

    def test_measurement_uses_deepest_observed_mount(self):
        disk = str(self.root).replace("\\", r"\134").replace(" ", r"\040")
        ram = str(self.root / "ram").replace("\\", r"\134").replace(" ", r"\040")
        mounts = f"1 0 0:1 / {disk} rw - overlay overlay rw\n2 1 0:2 / {ram} rw - tmpfs tmpfs rw\n"
        with patch.object(Path, "read_text", return_value=mounts):
            self.assertEqual(
                observed_filesystem(self.root / "ram/measurement"), "tmpfs"
            )
            self.assertEqual(
                observed_filesystem(self.root / "disk/measurement"), "overlay"
            )

    def test_measurement_decodes_mount_path_escapes(self):
        disk = str(self.root).replace("\\", r"\134").replace(" ", r"\040")
        ram = str(self.root / "test path").replace("\\", r"\134").replace(" ", r"\040")
        mounts = f"1 0 0:1 / {disk} rw - overlay overlay rw\n2 1 0:2 / {ram} rw - tmpfs tmpfs rw\n"
        with patch.object(Path, "read_text", return_value=mounts):
            self.assertEqual(
                observed_filesystem(self.root / "test path/measurement"), "tmpfs"
            )

    def test_unknown_measurement_mount_fails_closed(self):
        with (
            patch.object(Path, "read_text", return_value="unusable mount line\n"),
            self.assertRaisesRegex(RuntimeError, "not found"),
        ):
            observed_filesystem(self.root)

    def test_unreadable_measurement_mount_fails_closed(self):
        with (
            patch.object(
                Path, "read_text", side_effect=PermissionError("synthetic denial")
            ),
            self.assertRaisesRegex(RuntimeError, "Cannot observe"),
        ):
            observed_filesystem(self.root)

    def synthetic_consumer_case(self):
        # Deliberately fabricated UNIT DATA; never a VM execution receipt.
        return {
            "synthetic_unit_fixture": True,
            "program": "reconciliation",
            "variant": "good",
            "direction": "pandas->duckdb",
            "observed_exit_code": 0,
            "expected_exit_code": 0,
            "status": "PASS",
            "accepted": True,
            "published": True,
            "evidence_integrity_verified": True,
            "portable_verified_without_native_origin": True,
            "frozen_data_unchanged": True,
            "native_execution_count_complete": True,
            "dataset_manifest_sha256": "a" * 64,
            "native_result": {
                "executions": [{"engine": "pandas"}, {"engine": "duckdb"}]
            },
            "environment": {
                "python": "3.10.0 synthetic fixture",
                "machine": "aarch64",
                "isolated": 1,
                "optimized": 0,
            },
        }

    def case_review(self, case):
        self.file("case.json", json.dumps(case))
        review = self.review()
        review.candidate = {
            "files": {"consumer-data/manifest.json": {"sha256": "a" * 64}}
        }
        return review

    def test_synthetic_case_validator_checks_positive_structure_only(self):
        case = self.synthetic_consumer_case()
        case["environment"]["optimized"] = 1
        review = self.case_review(case)
        review.consumer_case(
            "case.json",
            "3.10",
            "reconciliation",
            "good",
            "pandas",
            "duckdb",
            optimized=True,
        )

    def test_consumer_unknown_native_count_cannot_pass(self):
        case = self.synthetic_consumer_case()
        case["native_execution_count_complete"] = False
        with self.assertRaisesRegex(ValueError, "coverage missing"):
            self.case_review(case).consumer_case(
                "case.json", "3.10", "reconciliation", "good", "pandas", "duckdb"
            )

    def test_consumer_peer_is_not_an_independent_second_engine(self):
        case = self.synthetic_consumer_case()
        case["native_result"]["executions"] = [
            {"engine": "pandas"},
            {"engine": "pandas"},
        ]
        with self.assertRaisesRegex(ValueError, "independent native"):
            self.case_review(case).consumer_case(
                "case.json", "3.10", "reconciliation", "good", "pandas", "duckdb"
            )

    def test_consumer_different_dataset_cannot_pass(self):
        case = self.synthetic_consumer_case()
        case["dataset_manifest_sha256"] = "b" * 64
        with self.assertRaisesRegex(ValueError, "different frozen dataset"):
            self.case_review(case).consumer_case(
                "case.json", "3.10", "reconciliation", "good", "pandas", "duckdb"
            )

    def test_consumer_optimized_flag_must_be_observed(self):
        case = self.synthetic_consumer_case()
        case["environment"]["optimized"] = 0
        with self.assertRaisesRegex(ValueError, "optimized"):
            self.case_review(case).consumer_case(
                "case.json",
                "3.10",
                "reconciliation",
                "good",
                "pandas",
                "duckdb",
                optimized=True,
            )

    def test_consumer_expected_rejections_remain_rejections(self):
        for variant, expected in (("defect", 1), ("not_evaluable", 3)):
            with self.subTest(variant=variant):
                case = self.synthetic_consumer_case()
                case.update(
                    variant=variant,
                    observed_exit_code=expected,
                    expected_exit_code=expected,
                    status="EXPECTED_REJECTION",
                    accepted=False,
                    published=False,
                )
                self.case_review(case).consumer_case(
                    "case.json", "3.10", "reconciliation", variant, "pandas", "duckdb"
                )
                case["published"] = True
                with self.assertRaisesRegex(ValueError, "acceptance/publication"):
                    self.case_review(case).consumer_case(
                        "case.json",
                        "3.10",
                        "reconciliation",
                        variant,
                        "pandas",
                        "duckdb",
                    )

    def test_consumer_x64_cannot_establish_arm64_pass(self):
        case = self.synthetic_consumer_case()
        case["environment"]["machine"] = "x86_64"
        with self.assertRaisesRegex(ValueError, "Python/platform/isolation"):
            self.case_review(case).consumer_case(
                "case.json", "3.10", "reconciliation", "good", "pandas", "duckdb"
            )


class VersionedScopeTests(unittest.TestCase):
    def candidate(self):
        from manifest_scope import CANDIDATE_V2, UNIVERSALITY_PYTHONS

        return {
            "schema": CANDIDATE_V2,
            "required_python_versions": list(UNIVERSALITY_PYTHONS),
        }

    def receipt(self):
        from manifest_scope import RECEIPT_V2, UNIVERSALITY_PYTHONS

        return {
            "schema": RECEIPT_V2,
            "required_python_versions": list(UNIVERSALITY_PYTHONS),
            "python_cells": [{"minor": minor} for minor in UNIVERSALITY_PYTHONS],
        }

    def test_legacy_scope_is_not_retroactively_four_versions(self):
        from manifest_scope import required_pythons, validate_cell_scope

        candidate = {"schema": "equiframe-maturity-candidate-1"}
        self.assertEqual(required_pythons(candidate), ("3.10", "3.12"))
        validate_cell_scope(
            candidate,
            {
                "schema": "equiframe-maturity-vm-execution-1",
                "python_cells": [{"minor": "3.10"}, {"minor": "3.12"}],
            },
        )

    def test_four_version_scope_is_explicit(self):
        from manifest_scope import validate_cell_scope

        self.assertEqual(
            validate_cell_scope(self.candidate(), self.receipt()),
            ("3.10", "3.11", "3.12", "3.13"),
        )

    def test_new_candidate_cannot_reduce_or_omit_scope(self):
        from manifest_scope import required_pythons

        for versions in (None, ["3.10", "3.12"], ["3.10", "3.11", "3.12", "3.12"]):
            candidate = self.candidate()
            candidate["required_python_versions"] = versions
            with self.subTest(versions=versions), self.assertRaises(ValueError):
                required_pythons(candidate)

    def test_missing_new_minor_cannot_pass(self):
        from manifest_scope import validate_cell_scope

        for minor in ("3.11", "3.13"):
            receipt = self.receipt()
            receipt["python_cells"] = [
                c for c in receipt["python_cells"] if c["minor"] != minor
            ]
            with self.subTest(minor=minor), self.assertRaises(ValueError):
                validate_cell_scope(self.candidate(), receipt)

    def test_duplicate_new_minor_cannot_pass(self):
        from manifest_scope import validate_cell_scope

        for minor in ("3.11", "3.13"):
            receipt = self.receipt()
            receipt["python_cells"][0] = {"minor": minor}
            with self.subTest(minor=minor), self.assertRaises(ValueError):
                validate_cell_scope(self.candidate(), receipt)

    def test_mixing_legacy_receipt_with_new_manifest_fails(self):
        from manifest_scope import validate_cell_scope

        receipt = self.receipt()
        receipt["schema"] = "equiframe-maturity-vm-execution-1"
        with self.assertRaises(ValueError):
            validate_cell_scope(self.candidate(), receipt)

    def test_receipt_scope_cannot_differ_from_manifest(self):
        from manifest_scope import validate_cell_scope

        receipt = self.receipt()
        receipt["required_python_versions"] = ["3.10", "3.12"]
        with self.assertRaises(ValueError):
            validate_cell_scope(self.candidate(), receipt)


class FinalIdentityTests(unittest.TestCase):
    setUp = HandoffToolsTests.setUp
    tearDown = HandoffToolsTests.tearDown
    file = HandoffToolsTests.file
    review = HandoffToolsTests.review
    synthetic_consumer_case = HandoffToolsTests.synthetic_consumer_case
    case_review = HandoffToolsTests.case_review

    def assert_runtime_identity_checks(self, scope):
        candidate = {
            "schema": "equiframe-maturity-candidate-2",
            "required_python_versions": ["3.10", "3.11", "3.12", "3.13"],
            "source": {},
            "artifact_hashes": {},
            "tooling_source": {"commit": "a" * 40},
            "files": {
                "scripts/run_vm_lab.py": {"sha256": "a" * 64},
                "locks/controller.lock": {"sha256": "b" * 64},
                "consumer-data/manifest.json": {"sha256": "c" * 64},
            },
            **candidate_scope(scope),
        }
        self.file("candidate.json", json.dumps(candidate))
        receipt = {
            "schema": receipt_schema(candidate),
            "cloud_validation_only": False,
            "candidate_manifest_sha256": sha(self.root / "candidate.json"),
            "source": {},
            "artifact_hashes": {},
            "tooling_source": candidate["tooling_source"],
            "script_hashes": {"scripts/run_vm_lab.py": "a" * 64},
            "controller_lock_sha256": "b" * 64,
            "data_manifest_sha256": "c" * 64,
            "kit_unchanged_after_run": True,
        }
        for key, wrong in (
            ("tooling_source", {}),
            ("script_hashes", {}),
            ("controller_lock_sha256", "0" * 64),
            ("data_manifest_sha256", "0" * 64),
            ("kit_unchanged_after_run", False),
        ):
            review = self.review()
            review.kit = self.root
            review.candidate = candidate
            review.receipt = {**receipt, key: wrong}
            with (
                self.subTest(key=key),
                self.assertRaisesRegex(ValueError, "identity differs"),
            ):
                review.validate()

    def test_new_receipt_rejects_changed_tooling_controller_input_or_unfinished_integrity(
        self,
    ):
        self.assert_runtime_identity_checks("universality")

    def test_original_m13_receipt_enforces_all_runtime_identity_guards(self):
        self.assert_runtime_identity_checks("original-m13-arm")

    def test_new_minor_claims_require_matching_observed_interpreter(self):
        for minor in ("3.11", "3.13"):
            case = self.synthetic_consumer_case()
            with (
                self.subTest(minor=minor),
                self.assertRaisesRegex(ValueError, "Python/platform/isolation"),
            ):
                self.case_review(case).consumer_case(
                    "case.json", minor, "reconciliation", "good", "pandas", "duckdb"
                )


if __name__ == "__main__":
    unittest.main()
