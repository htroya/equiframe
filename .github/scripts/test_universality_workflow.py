"""Structural tests for workflow candidate binding and the fixed 20-cell denominator."""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import unittest
import zipfile
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any
from unittest import mock

HERE = Path(__file__).resolve().parent


def load(name: str) -> ModuleType:
    specification = importlib.util.spec_from_file_location(name, HERE / (name + ".py"))
    if specification is None or specification.loader is None:
        raise RuntimeError("cannot load workflow helper")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def digest(path: Path) -> dict[str, object]:
    raw = path.read_bytes()
    return {"sha256": hashlib.sha256(raw).hexdigest(), "size_bytes": len(raw)}


def write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", "utf-8")


def process_is_running(pid: int) -> bool:
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel32.WaitForSingleObject.restype = wintypes.DWORD
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL
        handle = kernel32.OpenProcess(0x00100000, False, pid)
        if not handle:
            return False
        try:
            return int(kernel32.WaitForSingleObject(handle, 0)) == 0x00000102
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


class ControllerDurabilityTests(unittest.TestCase):
    runner = load("run_universality_cell")

    def recorder(self, root: Path, *, deadline_seconds: float = 30) -> Any:
        output = root / "evidence"
        output.mkdir()
        receipt: dict[str, Any] = {
            "schema": "test-cell",
            "status": "running",
            "commands": [],
            "errors": [],
        }
        return self.runner.Recorder(
            output,
            receipt,
            deadline_monotonic=time.monotonic() + deadline_seconds,
            evidence_reserve_seconds=1,
        )

    def assert_process_stopped(self, pid: int) -> None:
        deadline = time.monotonic() + 5
        while process_is_running(pid) and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertFalse(process_is_running(pid), f"process {pid} survived its container")

    def test_clean_environment_uses_an_explicit_noncredential_allowlist(self) -> None:
        source = {
            "PATH": os.environ.get("PATH", "test-path"),
            "HOME": "test-home",
            "SSL_CERT_FILE": "public-ca-path",
            "AWS_ACCESS_KEY_ID": "must-not-leak",
            "AWS_SECRET_ACCESS_KEY": "must-not-leak",
            "GH_PAT": "must-not-leak",
            "SSH_AUTH_SOCK": "must-not-leak",
            "HTTPS_PROXY": "https://credential@example.invalid",
            "UNEXPECTED_FUTURE_CREDENTIAL": "must-not-leak",
            "PYTHONPATH": "must-not-influence-tests",
        }
        with mock.patch.dict(os.environ, source, clear=True):
            environment = self.runner.clean_environment()

        self.assertEqual(environment["PATH"], source["PATH"])
        self.assertEqual(environment["HOME"], "test-home")
        self.assertEqual(environment["SSL_CERT_FILE"], "public-ca-path")
        self.assertEqual(environment["PYTHONUTF8"], "1")
        self.assertTrue(
            set(source) - {"PATH", "HOME", "SSL_CERT_FILE"}
            >= {
                "AWS_ACCESS_KEY_ID",
                "AWS_SECRET_ACCESS_KEY",
                "GH_PAT",
                "SSH_AUTH_SOCK",
                "HTTPS_PROXY",
                "UNEXPECTED_FUTURE_CREDENTIAL",
                "PYTHONPATH",
            }
        )
        for name in (
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY",
            "GH_PAT",
            "SSH_AUTH_SOCK",
            "HTTPS_PROXY",
            "UNEXPECTED_FUTURE_CREDENTIAL",
            "PYTHONPATH",
        ):
            self.assertNotIn(name, environment)

    def test_joint_test_tools_are_installed_before_the_binding_probe(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "benchmark"
            source.mkdir()
            (source / "pyproject.toml").write_text(
                '[dependency-groups]\ndev=["pytest>=9,<10", "hypothesis>=6,<7"]\n',
                "utf-8",
            )
            runtime_lock = root / "runtime.lock"
            runtime_lock.write_text("packaging==26.3 --hash=sha256:" + "1" * 64 + "\n", "utf-8")
            output = root / "evidence"
            joint = output / "joint"
            joint.mkdir(parents=True)

            class FakeRecorder:
                def __init__(self) -> None:
                    self.output = output
                    self.labels: list[str] = []

                def run(self, label: str, command: list[str], **_kwargs: object) -> Any:
                    self.labels.append(label)
                    if label == "joint-resolve-test-tools":
                        (joint / "test-tools.lock").write_text(
                            "pytest==9.1.1 --hash=sha256:" + "2" * 64 + "\n",
                            "utf-8",
                        )
                    if label == "joint-test-tools-binding":
                        self.assert_install_precedes_binding()
                        payload = {"versions": {"hypothesis": "6.168.3", "pytest": "9.1.1"}}
                        return subprocess.CompletedProcess(command, 0, json.dumps(payload), "")
                    return subprocess.CompletedProcess(command, 0, "", "")

                def assert_install_precedes_binding(self) -> None:
                    if self.labels.index("joint-install-test-tools") > self.labels.index(
                        "joint-test-tools-binding"
                    ):
                        raise AssertionError("binding ran before installation")

            recorder = FakeRecorder()
            contract = {"pytest_version": "9.1.1", "hypothesis_version": "6.168.3"}
            result = self.runner.add_test_tools(
                recorder,
                "uv",
                Path(sys.executable),
                runtime_lock,
                source,
                joint,
                (contract, contract),
            )
            self.assertEqual(
                recorder.labels,
                [
                    "joint-resolve-test-tools",
                    "joint-install-test-tools",
                    "joint-test-tools-binding",
                ],
            )
            self.assertEqual(
                result["versions"],
                {
                    "pytest": contract["pytest_version"],
                    "hypothesis": contract["hypothesis_version"],
                },
            )

    def test_recorder_removes_descendant_after_successful_leader_exit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            recorder = self.recorder(root)
            child_pid = root / "child.pid"
            program = (
                "import pathlib, subprocess, sys; "
                "child=subprocess.Popen([sys.executable, '-I', '-c', "
                "'import time; time.sleep(60)']); "
                "pathlib.Path(sys.argv[1]).write_text(str(child.pid), encoding='utf-8')"
            )
            recorder.run(
                "descendant-success",
                [sys.executable, "-I", "-c", program, str(child_pid)],
                timeout=10,
            )
            self.assertTrue(child_pid.is_file())
            self.assert_process_stopped(int(child_pid.read_text("utf-8")))
            self.assertEqual(recorder.receipt["commands"][0]["status"], "passed")

    def test_recorder_timeout_removes_complete_process_tree(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            recorder = self.recorder(root)
            child_pid = root / "timeout-child.pid"
            program = (
                "import pathlib, subprocess, sys, time; "
                "child=subprocess.Popen([sys.executable, '-I', '-c', "
                "'import time; time.sleep(60)']); "
                "pathlib.Path(sys.argv[1]).write_text(str(child.pid), encoding='utf-8'); "
                "time.sleep(60)"
            )
            with self.assertRaisesRegex(RuntimeError, "exceeded 3 seconds"):
                recorder.run(
                    "descendant-timeout",
                    [sys.executable, "-I", "-c", program, str(child_pid)],
                    timeout=3,
                )
            self.assertTrue(child_pid.is_file())
            self.assert_process_stopped(int(child_pid.read_text("utf-8")))
            self.assertEqual(recorder.receipt["commands"][0]["status"], "timeout")

    def test_work_window_preserves_evidence_reserve(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            recorder = self.recorder(root, deadline_seconds=2)
            recorder.evidence_reserve_seconds = 2
            with self.assertRaisesRegex(self.runner.CellDeadlineExceeded, "evidence reserve"):
                recorder.require_work_window("large operation", 1)

    def test_cleanup_failure_still_writes_inventory_and_attestation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            recorder = self.recorder(root)
            work = recorder.output / "work"
            work.mkdir()
            (work / "temporary.txt").write_text("temporary\n", "utf-8")
            attestation = root / "attestation"
            original_remove_tree = self.runner.remove_tree

            def fail_work_cleanup(path: Path) -> None:
                if path == work:
                    raise PermissionError("simulated locked work tree")
                original_remove_tree(path)

            with mock.patch.object(self.runner, "remove_tree", side_effect=fail_work_cleanup):
                exit_code, inventory = self.runner.finalize_cell(
                    recorder,
                    recorder.receipt,
                    work=work,
                    kept_environment=None,
                    attestation_output=attestation,
                    exit_code=0,
                )
            self.assertEqual(exit_code, 1)
            self.assertEqual(recorder.receipt["status"], "failed")
            self.assertIn(
                "cleanup_work",
                {entry.get("stage") for entry in recorder.receipt["errors"]},
            )
            self.assertIn("receipt.json", inventory["files"])
            self.assertTrue((recorder.output / "receipt.json").is_file())
            self.assertTrue((recorder.output / "evidence-inventory.json").is_file())
            self.assertTrue((attestation / "receipt.json").is_file())
            self.assertTrue((attestation / "evidence-inventory.json").is_file())

    def test_inventory_excludes_only_root_inventory_and_includes_hidden_members(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            root_inventory = output / "evidence-inventory.json"
            root_inventory.write_text("root self reference\n", "utf-8")
            hidden = output / "nested/.hidden"
            hidden.parent.mkdir()
            hidden.write_text("hidden evidence\n", "utf-8")
            nested_inventory = output / "nested/evidence-inventory.json"
            nested_inventory.write_text("nested evidence\n", "utf-8")

            inventory = self.runner.inventory_evidence(output)

            self.assertNotIn("evidence-inventory.json", inventory["files"])
            self.assertEqual(inventory["files"]["nested/.hidden"], digest(hidden))
            self.assertEqual(
                inventory["files"]["nested/evidence-inventory.json"],
                digest(nested_inventory),
            )

    def test_archive_paths_reject_windows_reserved_names_and_case_collisions(
        self,
    ) -> None:
        for names in (
            ["package/CON.txt"],
            ["package/module.py", "PACKAGE/MODULE.py"],
            ["package/value:stream"],
            ["package/trailing. "],
        ):
            with self.subTest(names=names), self.assertRaises(ValueError):
                self.runner.portable_archive_inventory(names)


class UniversalityWorkflowTests(unittest.TestCase):
    aggregate = load("aggregate_universality")
    prepare = load("prepare_universality_candidate")

    def candidate(
        self, root: Path, run_id: str, run_attempt: str = "1"
    ) -> tuple[Path, dict[str, object], str]:
        candidate = root / "candidate"
        candidate.mkdir()
        payload = candidate / "payload.txt"
        payload.write_text("exact artifact bytes\n", "utf-8")
        source = {
            "equiframe": {
                "repository": "owner/core",
                "commit": "a" * 40,
                "tree": "b" * 40,
            },
            "consumer": {
                "repository": "owner/app",
                "commit": "c" * 40,
                "tree": "d" * 40,
            },
            "consumer_data": {
                "repository": "owner/data",
                "commit": "e" * 40,
                "tree": "f" * 40,
            },
        }
        artifact_record = digest(payload)
        artifacts: dict[str, object] = {
            "core": {
                "version": "1.0",
                "wheel_record": artifact_record,
                "sdist_record": artifact_record,
            },
            "benchmark": {
                "version": "1.0",
                "wheel_record": artifact_record,
                "sdist_record": artifact_record,
            },
            "consumer": {
                "version": "1.0",
                "wheel_record": artifact_record,
                "sdist_record": artifact_record,
            },
        }
        test_manifests: dict[str, object] = {}
        candidate_files = {"payload.txt": digest(payload)}
        for key, package in (
            ("core", "equiframe"),
            ("benchmark", "equiframe-benchmark"),
            ("consumer", "equiframe-consumer-lab"),
        ):
            identities = [(f"tests.test_{key}", f"test_{key}")]
            if key == "benchmark":
                identities.extend(
                    sorted(
                        {
                            (classname, name)
                            for system in ("Linux", "Windows", "Darwin")
                            for python in self.aggregate.PYTHONS
                            for classname, name, _message in self.aggregate.benchmark_skip_contract(
                                system, python
                            )
                        }
                    )
                )
            if key == "core":
                identities.append(("tests.test_core_extra", "test_core_extra"))
            test_document = {
                "schema": "equiframe-test-manifest-1",
                "package": package,
                "pytest_version": "9.1.1",
                "hypothesis_version": "6.142.4",
                "plugin_autoload_disabled": True,
                "files": {
                    f"tests/test_{key}_{index}.py": {
                        "sha256": "1" * 64,
                        "size_bytes": 1,
                    }
                    for index in range(len(identities))
                },
                "tests": [
                    {
                        "nodeid": f"tests/test_{key}_{index}.py::{identity[1]}",
                        "classname": identity[0],
                        "name": identity[1],
                    }
                    for index, identity in enumerate(identities)
                ],
                "test_count": len(identities),
            }
            path = candidate / "test-manifests" / f"{package}.json"
            write(path, test_document)
            relative = path.relative_to(candidate).as_posix()
            candidate_files[relative] = digest(path)
            encoded = json.dumps(sorted(identities), separators=(",", ":")).encode("utf-8")
            test_manifests[key] = {
                "path": relative,
                "record": digest(path),
                "test_count": len(identities),
                "junit_identities_sha256": hashlib.sha256(encoded).hexdigest(),
                "pytest_version": "9.1.1",
                "hypothesis_version": "6.142.4",
            }
        document = {
            "schema": "equiframe-universality-actions-candidate-1",
            "credentials_included": False,
            "results_included": False,
            "source": source,
            "workflow_execution": {
                "provider": "github-actions",
                "run_id": run_id,
                "run_attempt": run_attempt,
                "repository": "owner/core",
                "workflow_ref": ("owner/core/.github/workflows/equiframe.yml@refs/heads/test"),
                "workflow_sha": "a" * 40,
            },
            "artifacts": artifacts,
            "test_manifests": test_manifests,
            "files": candidate_files,
            "required_python_versions": list(self.aggregate.PYTHONS),
            "required_native_platforms": [
                {"system": system, "architecture": architecture}
                for _label, system, architecture in self.aggregate.PLATFORMS
            ],
        }
        write(candidate / "candidate.json", document)
        return (
            candidate,
            document,
            hashlib.sha256((candidate / "candidate.json").read_bytes()).hexdigest(),
        )

    def consumer_summary(self, version: str, *, optimized: bool = False) -> dict[str, Any]:
        records: list[dict[str, Any]] = []
        index = 0
        for program in self.aggregate.CONSUMER_PROGRAMS:
            for source, target in self.aggregate.CONSUMER_DIRECTIONS:
                for variant in self.aggregate.CONSUMER_VARIANTS:
                    index += 1
                    case_id = f"{index:03d}-{program}-{source}-{target}-{variant}"
                    accepted = variant == "good"
                    exit_code = self.aggregate.CONSUMER_EXIT_CODES[variant]
                    records.append(
                        {
                            "case_id": case_id,
                            "program": program,
                            "variant": variant,
                            "source": source,
                            "target": target,
                            "command": [
                                "/opt/python/bin/python",
                                "-I",
                                *(["-O"] if optimized else []),
                                "-m",
                                "equiframe_consumer_lab",
                                "run",
                                "--program",
                                program,
                                "--variant",
                                variant,
                                "--source",
                                source,
                                "--target",
                                target,
                                "--data",
                                "/tmp/frozen-data",
                                "--output",
                                (
                                    f"/tmp/consumer-72-optimized/cases/{case_id}"
                                    if optimized
                                    else f"/tmp/consumer-72/cases/{case_id}"
                                ),
                            ],
                            "expected_exit": exit_code,
                            "actual_exit": exit_code,
                            "process_outcome": "completed",
                            "process_error": None,
                            "receipt_error": None,
                            "logs_error": None,
                            "unwritten_stdout": None,
                            "unwritten_stderr": None,
                            "accepted": accepted,
                            "published": accepted,
                            "status": "PASS" if accepted else "EXPECTED_REJECTION",
                            "harness_pass": True,
                            "elapsed_seconds": 0.25,
                            "case_receipt": f"cases/{case_id}/case.json",
                        }
                    )
        return {
            "consumer_version": version,
            "status": "PASS",
            "planned_cases": 72,
            "distinct_cases": 72,
            "attempted_cases": 72,
            "case_launch_attempts": 72,
            "case_subprocesses": 72,
            "completed_case_processes": 72,
            "not_attempted_cases": 0,
            "not_run_cases": 0,
            "cases_with_valid_receipts": 72,
            "native_execution_attempts": 144,
            "recorded_native_executions": 144,
            "cases_with_unavailable_native_count": 0,
            "case_status_counts": {"PASS": 24, "EXPECTED_REJECTION": 48, "FAIL": 0},
            "accepted_cases": 24,
            "rejected_cases": 48,
            "cases_with_unavailable_acceptance": 0,
            "optimization_required": optimized,
            "optimized": optimized,
            "all_expected_outcomes_observed": True,
            "terminal_errors": [],
            "note": self.aggregate.CONSUMER_SUMMARY_NOTE,
            "records": records,
        }

    def measurement_documents(
        self, requested: dict[str, str]
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        platform_name = self.aggregate.MEASUREMENT_PLATFORM[requested["system"]]
        filesystem_by_system = {
            "Linux": (
                "ext4",
                "linux_proc_self_mountinfo",
                "current_mount_namespace",
                "/",
            ),
            "Windows": (
                "NTFS",
                "windows_get_volume_information_and_drive_type",
                "fixed",
                "C:\\",
            ),
            "Darwin": (
                "apfs",
                "macos_sbin_mount_table",
                "mount_table_filesystem_type",
                "/",
            ),
        }
        filesystem, filesystem_method, backing, mount_point = filesystem_by_system[
            requested["system"]
        ]
        machine = "x86_64" if requested["architecture"] == "x64" else "aarch64"
        protocol = {
            "rows": [100, 1000],
            "width": 2,
            "repetitions": 3,
            "rss_budget_bytes": 512 * 1024**2,
            "disk_budget_bytes": 64 * 1024**2,
            "timeout_seconds": 120,
            "supervisor_sample_interval_seconds": 0.25,
            "threads_per_engine": 1,
            "expected_state": "different",
            "storage": "disk",
            "filesystem_observed": filesystem,
            "filesystem_observation": {
                "filesystem": filesystem,
                "storage": "disk",
                "method": filesystem_method,
                "mount_point": mount_point,
                "backing_kind": backing,
                "limitations": ["Exact native filesystem observation limitation."],
            },
            "resource_measurement_contract": {
                "id": self.aggregate.MEASUREMENT_CONTRACT_ID,
                "platform": platform_name,
            },
            "concurrent_known_loads": (
                "No other task-controlled suite; shared host not controlled"
            ),
            "os_cache": "uncontrolled",
            "slo_accepted": False,
            "scope": ("local synthetic capture/compare/evidence; no network transport or VM claim"),
            "python": requested["python"] + ".99",
            "machine": machine,
            "executable": "/opt/python/bin/python",
        }
        fixed_sources = {
            "sampled_rss_peak_bytes": "psutil_process_memory_info_rss",
            "cpu_user_seconds": "psutil_process_cpu_times_user",
            "cpu_system_seconds": "psutil_process_cpu_times_system",
            "disk_apparent_peak_bytes": "filesystem_tree_stat_size",
            "disk_allocated_peak_bytes": "filesystem_tree_stat_blocks_512",
        }
        unavailable = self.aggregate.MEASUREMENT_UNAVAILABLE[platform_name]
        metric_records: list[dict[str, Any]] = []
        values: dict[str, int | float | None] = {}
        for metric in self.aggregate.MEASUREMENT_METRICS:
            reason = unavailable.get(metric)
            if reason is not None:
                metric_records.append(
                    {
                        "schema_version": "1.0",
                        "metric": metric,
                        "state": "unavailable_on_platform",
                        "source": None,
                        "reason": reason,
                    }
                )
                values[metric] = None
                continue
            source = fixed_sources.get(metric, "psutil_process_io_counters")
            metric_records.append(
                {
                    "schema_version": "1.0",
                    "metric": metric,
                    "state": "observed",
                    "source": source,
                    "reason": None,
                }
            )
            values[metric] = 0.5 if metric.endswith("_seconds") else 1024
        contract = {
            "id": self.aggregate.MEASUREMENT_CONTRACT_ID,
            "platform": platform_name,
            "metrics": metric_records,
        }
        termination_scope = (
            "direct_child" if requested["system"] == "Windows" else "posix_process_group"
        )
        results = []
        for index, rows in enumerate((100, 1000), start=1):
            process = {
                **values,
                "pid": 4000 + index,
                "exit_code": 0,
                "termination_reason": "exited",
                "wall_seconds": 1.0,
                "io_counter_source": "unavailable" if platform_name == "macos" else "psutil",
                "io_counter_fallback_reason": None,
                "measurement_contract": self.aggregate.MEASUREMENT_CONTRACT_ID,
                "measurement_platform": platform_name,
                "metric_coverage": json.loads(json.dumps(metric_records)),
                "sample_interval_seconds": 0.25,
                "max_sample_gap_seconds": 0.3,
                "sample_count": 4,
                "monitoring_errors": [],
                "cleanup_reaped": True,
                "observed_descendant_pids": [],
                "resource_scope": "direct_child_excluding_descendants",
                "termination_scope": termination_scope,
                "rss_method": "sampled_absolute_lower_bound",
                "counter_method": "sampled_cumulative_last_available",
                "disk_method": "sampled_tree_inodes_no_symlink_following",
                "budget_method": "reactive_sampled_thresholds_not_hard_quotas",
            }
            results.append(
                {
                    "run_id": "scale-" + str(index) * 32,
                    "case_id": f"maturity-{rows}",
                    "complete": True,
                    "resource_measurement_complete": True,
                    "resource_measurement_contract": json.loads(json.dumps(contract)),
                    "requested_repetitions": 3,
                    "observed_repetitions": 3,
                    "correct_complete_repetitions": 3,
                    "unsuccessful_or_missing_repetitions": 0,
                    "resource_quality": ["complete", "complete", "complete"],
                    "process": process,
                    "statistics_by_cache": {
                        "fresh_process_os_cache_uncontrolled": {"n": 1},
                        "warm_process_os_cache_uncontrolled": {"n": 2},
                    },
                    "issues": [],
                }
            )
        summary = {"protocol": json.loads(json.dumps(protocol)), "results": results}
        bounded_limit = {
            "scope": "output_schema",
            "state": "not_evaluable",
            "complete": False,
            "reference": "expected",
            "strategy": "pending",
            "right": None,
            "counts": {
                "final": False,
                "difference_records": 0,
                "contract_violations": 0,
            },
            "options": {"max_rows": 1},
            "diagnostics": [
                {
                    "code": "resource_exhausted",
                    "message": "max_rows (combined inputs)",
                    "side": "left",
                    "exception_type": "ResourceLimitError",
                }
            ],
        }
        return protocol, summary, bounded_limit

    def cells(
        self,
        root: Path,
        candidate: dict[str, Any],
        candidate_hash: str,
        run_id: str,
        run_attempt: str = "1",
    ) -> Path:
        cells = root / "cells"
        cells.mkdir()
        for name, requested in self.aggregate.EXPECTED.items():
            directory = cells / (f"universality-cell-{name}-{run_id}-{run_attempt}")
            directory.mkdir()
            requirements_copy = directory / "toolchain/controller-requirements.txt"
            requirements_copy.parent.mkdir()
            requirements_copy.write_text("uv==0.12.19 --hash=sha256:" + "6" * 64 + "\n", "utf-8")
            joint = directory / "joint-all-latest"
            measurements = joint / "measurements"
            measurements.mkdir(parents=True)
            (joint / "test-tools.lock").write_text(
                "hypothesis==6.142.4 --hash=sha256:" + "7" * 64 + "\n"
                "pytest==9.1.1 --hash=sha256:" + "8" * 64 + "\n",
                "utf-8",
            )
            summary = self.consumer_summary(str(candidate["artifacts"]["consumer"]["version"]))
            write(joint / "consumer-72/summary.json", summary)
            optimized_summary = self.consumer_summary(
                str(candidate["artifacts"]["consumer"]["version"]),
                optimized=True,
            )
            write(
                joint / "consumer-72-optimized/summary.json",
                optimized_summary,
            )
            protocol, measurement_summary, bounded_limit = self.measurement_documents(requested)
            write(measurements / "protocol.json", protocol)
            write(measurements / "summary.json", measurement_summary)
            write(measurements / "bounded-limit.json", bounded_limit)
            write(
                joint / "consumer-faults/fault-checks.json",
                {
                    "status": "PASS",
                    "environment": {"isolated": 1, "optimized": 1},
                    "synthetic_fixture": True,
                    "checks": [
                        {
                            "case": "accept",
                            "state": "equivalent",
                            "accepted": True,
                            "error": None,
                        },
                        {
                            "case": "compensated_reject",
                            "state": "different",
                            "accepted": False,
                            "error": "EquivalenceAssertionError",
                        },
                        {
                            "case": "budget_reject",
                            "state": "not_evaluable",
                            "accepted": False,
                            "error": "EquivalenceAssertionError",
                        },
                        {
                            "case": "rejected_input",
                            "prior_publication_preserved": True,
                            "staging_clean": True,
                        },
                        {
                            "case": "write_fault",
                            "prior_publication_preserved": True,
                            "staging_clean": True,
                        },
                        {"case": "report_corruption", "rejected": True},
                    ],
                },
            )
            comparison_expectation = tuple[str, bool, bool, bool, int, int, list[str]]
            h_expectations: dict[str, tuple[int, str, list[comparison_expectation]]] = {
                "good": (
                    0,
                    "passed",
                    [
                        ("equivalent", True, True, True, 0, 0, []),
                        ("equivalent", True, True, True, 0, 0, []),
                    ],
                ),
                "different": (
                    1,
                    "failed",
                    [
                        ("equivalent", True, True, True, 0, 0, []),
                        ("different", True, True, False, 1, 1, []),
                    ],
                ),
                "not_evaluable": (
                    3,
                    "not_evaluable",
                    [
                        (
                            "not_evaluable",
                            False,
                            False,
                            False,
                            3,
                            0,
                            ["resource_exhausted"],
                        ),
                        (
                            "not_evaluable",
                            False,
                            False,
                            False,
                            3,
                            0,
                            ["resource_exhausted"],
                        ),
                    ],
                ),
            }
            optimized_h: dict[str, Any] = {}
            for scenario, expected_exit in {
                "good": 0,
                "different": 1,
                "not_evaluable": 3,
                "error": 2,
            }.items():
                h_path = joint / f"optimized-H-{scenario}/summary.json"
                h_summary: dict[str, Any] = {
                    "journey": "H",
                    "synthetic": True,
                    "scenario": scenario,
                    "accepted": scenario == "good",
                    "exit_code": expected_exit,
                    "integrity": "rejected" if scenario == "error" else "passed",
                    "report_created": scenario != "error",
                    "original_paths_available": False,
                }
                if scenario != "error":
                    state, comparisons = h_expectations[scenario][1:]
                    bundle_path = joint / f"optimized-H-{scenario}/portable/bundle.json"
                    write(bundle_path, {"scenario": scenario, "closed_inventory": True})
                    h_summary.update(
                        operational_state=state,
                        bundle_manifest_sha256=hashlib.sha256(bundle_path.read_bytes()).hexdigest(),
                        independent_review="not_requested",
                        comparisons=[
                            {
                                "state": comparison[0],
                                "complete": comparison[1],
                                "counts_final": comparison[2],
                                "accepted": comparison[3],
                                "exit_code": comparison[4],
                                "difference_records": comparison[5],
                                "diagnostic_codes": comparison[6],
                                "report": f"reports/comparison-{index}/report.html",
                            }
                            for index, comparison in enumerate(comparisons)
                        ],
                    )
                write(h_path, h_summary)
                scenario_receipt = {
                    "path": h_path.relative_to(directory).as_posix(),
                    "record": digest(h_path),
                }
                if scenario != "error":
                    scenario_receipt.update(
                        bundle_manifest=bundle_path.relative_to(directory).as_posix(),
                        bundle_manifest_record=digest(bundle_path),
                    )
                optimized_h[scenario] = scenario_receipt
            versions = {
                "equiframe": "1.0",
                "equiframe-benchmark": "1.0",
                "equiframe-consumer-lab": "1.0",
            }
            write(joint / "installed-pair.json", {"versions": versions})
            rebuild = directory / "sdist-rebuild"
            rebuild.mkdir()
            build_versions = {"build": "1.3.0", "hatchling": "1.28.0"}
            runtime_versions = {"typing-extensions": "4.15.0"}
            (rebuild / "build-tools.lock").write_text(
                "build==1.3.0 --hash=sha256:" + "1" * 64 + "\n"
                "hatchling==1.28.0 --hash=sha256:" + "2" * 64 + "\n",
                "utf-8",
            )
            (rebuild / "runtime.lock").write_text(
                "typing-extensions==4.15.0 --hash=sha256:" + "3" * 64 + "\n",
                "utf-8",
            )
            installed_versions = {**runtime_versions, **versions}
            installed_binding = {
                "versions": installed_versions,
                "paths": {distribution: f"/venv/{distribution}" for distribution in versions},
                "python": requested["python"] + ".0",
                "system": requested["system"],
                "machine": requested["architecture"],
            }
            api_probe = {
                "accepted": True,
                "complete": True,
                "difference_records": 0,
                "state": "equivalent",
                "versions": versions,
            }
            write(rebuild / "installed-binding.json", installed_binding)
            write(rebuild / "api-probe.json", api_probe)
            rebuild_labels = {
                "sdist-resolve-build-tools",
                "sdist-build-tools-venv",
                "sdist-install-build-tools",
                "sdist-build-tools-binding",
                "sdist-rebuild-core",
                "sdist-rebuild-benchmark",
                "sdist-rebuild-consumer",
                "sdist-rebuild-runtime-venv",
                "sdist-rebuild-install-runtime",
                "sdist-rebuild-install-wheels",
                "sdist-rebuild-pip-check",
                "sdist-rebuild-binding",
                "sdist-rebuild-api",
                "sdist-rebuild-cli-equiframe",
                "sdist-rebuild-cli-equiframe-benchmark",
                "sdist-rebuild-cli-equiframe-consumer-lab",
            }
            required_labels = {
                "toolchain-uv-version",
                "joint-resolve-test-tools",
                "joint-install-test-tools",
                "joint-test-tools-binding",
                "joint-pip-check",
                "benchmark-installed-suite",
                "consumer-installed-suite",
                "optimized-H-good",
                "optimized-H-different",
                "optimized-H-not_evaluable",
                "optimized-H-error",
                "bounded-measurements",
                "consumer-72-cases",
                "consumer-72-optimized-cases",
                "consumer-fault-checks",
                "installed-pair-binding",
            } | rebuild_labels
            artifact_record = candidate["artifacts"]["core"]["wheel_record"]
            distribution_files = {"package/member.py": artifact_record}
            distribution_digest = hashlib.sha256(
                json.dumps(distribution_files, sort_keys=True, separators=(",", ":")).encode(
                    "utf-8"
                )
            ).hexdigest()
            distributions = {
                package: {
                    "name": package,
                    "version": version,
                    "file_count": 1,
                    "files_sha256": distribution_digest,
                    "files": distribution_files,
                }
                for package, version in self.aggregate.PINNED_TOOLCHAIN.items()
            }
            wheel_identity = {
                "distribution": "placeholder",
                "version": "1.0",
                "build_tag": [],
                "tags": ["py3-none-any"],
                "member_count": 10,
                "installed_member_count": 9,
                "installed_payload_sha256": "4" * 64,
                "record_valid": True,
            }
            rebuild_packages: dict[str, Any] = {}
            for key, distribution in (
                ("core", "equiframe"),
                ("benchmark", "equiframe-benchmark"),
                ("consumer", "equiframe-consumer-lab"),
            ):
                identity = {**wheel_identity, "distribution": distribution}
                rebuild_packages[key] = {
                    "distribution": distribution,
                    "version": "1.0",
                    "source_sdist": artifact_record,
                    "candidate_wheel": artifact_record,
                    "candidate_identity": identity,
                    "rebuilt_wheel_path": (
                        f"sdist-rebuild/rebuilt-wheels/{distribution}-1.0-py3-none-any.whl"
                    ),
                    "rebuilt_wheel": artifact_record,
                    "rebuilt_identity": identity,
                    "installed_payload_match": True,
                }
            command_labels = sorted(required_labels)
            commands = [{"label": label, "status": "passed"} for label in command_labels]
            rebuild_receipt = {
                "schema": "equiframe-universality-sdist-rebuild-1",
                "status": "passed",
                "started_at": "2026-10-09T00:00:00+00:00",
                "finished_at": "2026-10-09T00:01:00+00:00",
                "errors": [],
                "packages": rebuild_packages,
                "build_systems": {
                    key: {
                        "backend": "hatchling.build",
                        "requirements": {"hatchling": "1.28.0"},
                    }
                    for key in ("core", "benchmark", "consumer")
                },
                "build_tools": {
                    "frontend": {"name": "build", "version": "1.3.0"},
                    "lock": "sdist-rebuild/build-tools.lock",
                    "lock_record": digest(rebuild / "build-tools.lock"),
                    "versions": build_versions,
                    "binding": {
                        "versions": build_versions,
                        "paths": {},
                        "python": requested["python"] + ".0",
                        "system": requested["system"],
                        "machine": requested["architecture"],
                    },
                },
                "installation": {
                    "runtime_lock": "sdist-rebuild/runtime.lock",
                    "runtime_lock_record": digest(rebuild / "runtime.lock"),
                    "runtime_versions": runtime_versions,
                    "binding": installed_binding,
                    "binding_path": "sdist-rebuild/installed-binding.json",
                    "binding_record": digest(rebuild / "installed-binding.json"),
                    "api_probe": api_probe,
                    "api_probe_path": "sdist-rebuild/api-probe.json",
                    "api_probe_record": digest(rebuild / "api-probe.json"),
                    "cli": {
                        entry_point: {"entry_point": entry_point, "status": "passed"}
                        for entry_point in versions
                    },
                    "pip_check": "passed",
                },
                "command_indexes": [
                    index for index, label in enumerate(command_labels) if label in rebuild_labels
                ],
            }
            write(rebuild / "receipt.json", rebuild_receipt)
            expected_benchmark_skips = self.aggregate.skip_records(
                self.aggregate.benchmark_skip_contract(requested["system"], requested["python"])
            )
            expected_core_skips = self.aggregate.core_skip_records(requested["system"])
            core_profiles: list[dict[str, Any]] = []
            for profile in self.aggregate.CORE_PROFILES:
                for endpoint in self.aggregate.ENDPOINTS:
                    core_profile = {
                        "profile": profile,
                        "endpoint": endpoint,
                        "status": "passed",
                    }
                    if profile == "all":
                        core_manifest = candidate["test_manifests"]["core"]
                        core_profile["installed_suite"] = {
                            "accepted": True,
                            "tests": core_manifest["test_count"],
                            "failures": 0,
                            "errors": 0,
                            "skipped": len(expected_core_skips),
                            "xfail": 0,
                            "expected_skips": expected_core_skips,
                            "observed_skips": expected_core_skips,
                            "identity_contract_matches": True,
                            "junit_identities_sha256": core_manifest["junit_identities_sha256"],
                        }
                    core_profiles.append(core_profile)
            receipt = {
                "schema": "equiframe-universality-actions-cell-1",
                "status": "passed",
                "requested": requested,
                "actual": {**requested, "python_full": requested["python"] + ".0"},
                "candidate_manifest_sha256": candidate_hash,
                "source": candidate["source"],
                "artifacts": candidate["artifacts"],
                "execution": {
                    **candidate["workflow_execution"],
                    "job": "native-cell",
                    "runner_name": f"runner-{name}",
                    "runner_os": (
                        "macOS" if requested["system"] == "Darwin" else requested["system"]
                    ),
                    "runner_arch": ("X64" if requested["architecture"] == "x64" else "ARM64"),
                    "runner_environment": "github-hosted",
                    "runner_image_os": "fixture-" + requested["system"].lower(),
                    "runner_image_version": "20261009.1",
                    "cell_id": name,
                },
                "deadline_seconds": 19_800,
                "receipts_authenticated": False,
                "toolchain": {
                    "packages": self.aggregate.PINNED_TOOLCHAIN,
                    "distributions": distributions,
                    "requirements": {
                        "path": "toolchain/controller-requirements.txt",
                        "record": digest(requirements_copy),
                    },
                    "python_version": requested["python"] + ".0",
                    "python_implementation": "CPython",
                    "pip_version": "26.0.1",
                    "python_executable": artifact_record,
                    "uv_executable": artifact_record,
                    "uv_path": "/opt/toolcache/uv",
                },
                "errors": [],
                "commands": commands,
                "sdist_rebuild": {
                    "status": "passed",
                    "receipt": "sdist-rebuild/receipt.json",
                    "receipt_record": digest(rebuild / "receipt.json"),
                },
                "core_profiles": core_profiles,
                "benchmark_profiles": [
                    {"profile": profile, "endpoint": endpoint, "status": "passed"}
                    for profile in self.aggregate.BENCHMARK_PROFILES
                    for endpoint in self.aggregate.ENDPOINTS
                ],
                "joint": {
                    "status": "passed",
                    "errors": [],
                    "test_tools": {
                        "versions": {"hypothesis": "6.142.4", "pytest": "9.1.1"},
                        "binding": {
                            "versions": {"hypothesis": "6.142.4", "pytest": "9.1.1"},
                            "paths": {
                                "hypothesis": "/site-packages/hypothesis",
                                "pytest": "/site-packages/pytest",
                            },
                            "python": requested["python"] + ".0",
                            "system": requested["system"],
                            "machine": requested["architecture"],
                        },
                        "lock": "joint-all-latest/test-tools.lock",
                        "lock_record": digest(joint / "test-tools.lock"),
                    },
                    "benchmark_suite": {
                        "accepted": True,
                        "tests": candidate["test_manifests"]["benchmark"]["test_count"],
                        "failures": 0,
                        "errors": 0,
                        "skipped": len(expected_benchmark_skips),
                        "expected_skips": expected_benchmark_skips,
                        "observed_skips": expected_benchmark_skips,
                        "identity_contract_matches": True,
                        "junit_identities_sha256": candidate["test_manifests"]["benchmark"][
                            "junit_identities_sha256"
                        ],
                    },
                    "consumer_suite": {
                        "accepted": True,
                        "tests": candidate["test_manifests"]["consumer"]["test_count"],
                        "failures": 0,
                        "errors": 0,
                        "skipped": 0,
                        "expected_skips": [],
                        "observed_skips": [],
                        "identity_contract_matches": True,
                        "junit_identities_sha256": candidate["test_manifests"]["consumer"][
                            "junit_identities_sha256"
                        ],
                    },
                    "consumer_summary": "joint-all-latest/consumer-72/summary.json",
                    "consumer_summary_record": digest(joint / "consumer-72/summary.json"),
                    "consumer_optimized_summary": (
                        "joint-all-latest/consumer-72-optimized/summary.json"
                    ),
                    "consumer_optimized_summary_record": digest(
                        joint / "consumer-72-optimized/summary.json"
                    ),
                    "measurement": {
                        "status": "passed",
                        "protocol": digest(measurements / "protocol.json"),
                        "summary": digest(measurements / "summary.json"),
                        "bounded_limit": digest(measurements / "bounded-limit.json"),
                    },
                    "consumer_faults": {
                        "path": "joint-all-latest/consumer-faults/fault-checks.json",
                        "record": digest(joint / "consumer-faults/fault-checks.json"),
                    },
                    "optimized_h": optimized_h,
                    "installed_pair": digest(joint / "installed-pair.json"),
                    "artifact_records": {
                        "core": artifact_record,
                        "benchmark": artifact_record,
                        "consumer": artifact_record,
                    },
                },
            }
            write(directory / "receipt.json", receipt)
            files = {
                path.relative_to(directory).as_posix(): digest(path)
                for path in directory.rglob("*")
                if path.is_file()
            }
            write(
                directory / "evidence-inventory.json",
                {
                    "schema": "equiframe-universality-evidence-inventory-1",
                    "files": files,
                    "unsigned": True,
                },
            )
        return cells

    def execute(
        self,
        candidate: Path,
        cells: Path,
        output: Path,
        run_id: str,
        run_attempt: str = "1",
        *,
        candidate_result: str = "success",
        matrix_result: str = "success",
    ) -> int:
        return subprocess.run(
            [
                sys.executable,
                str(HERE / "aggregate_universality.py"),
                "--candidate",
                str(candidate),
                "--cells",
                str(cells),
                "--run-id",
                run_id,
                "--run-attempt",
                run_attempt,
                "--github-repository",
                "owner/core",
                "--github-workflow-ref",
                "owner/core/.github/workflows/equiframe.yml@refs/heads/test",
                "--github-workflow-sha",
                "a" * 40,
                "--candidate-job-result",
                candidate_result,
                "--matrix-job-result",
                matrix_result,
                "--output",
                str(output),
            ],
            check=False,
            capture_output=True,
            text=True,
            env={
                **os.environ,
                "GITHUB_ACTIONS": "true",
                "GITHUB_RUN_ID": run_id,
                "GITHUB_RUN_ATTEMPT": run_attempt,
                "GITHUB_JOB": "aggregate",
                "GITHUB_REPOSITORY": "owner/core",
                "GITHUB_WORKFLOW_REF": (
                    "owner/core/.github/workflows/equiframe.yml@refs/heads/test"
                ),
                "GITHUB_WORKFLOW_SHA": "a" * 40,
            },
        ).returncode

    def test_aggregate_requires_and_accepts_exactly_twenty_bound_cells(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            candidate, document, candidate_hash = self.candidate(root, "42")
            cells = self.cells(root, document, candidate_hash, "42")
            output = root / "aggregate"
            self.assertEqual(self.execute(candidate, cells, output, "42"), 0)
            receipt = json.loads((output / "matrix-receipt.json").read_text("utf-8"))
            self.assertEqual(receipt["status"], "passed")
            self.assertEqual(receipt["counts"], {"failed": 0, "passed": 20, "running": 0})

    def test_aggregate_rejects_authenticated_measurement_semantic_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            candidate, document, candidate_hash = self.candidate(root, "422")
            cells = self.cells(root, document, candidate_hash, "422")
            cell = next(iter(self.aggregate.EXPECTED))
            directory = cells / f"universality-cell-{cell}-422-1"
            summary_path = directory / "joint-all-latest/measurements/summary.json"
            summary = json.loads(summary_path.read_text("utf-8"))
            summary["results"][0]["process"]["monitoring_errors"].append("cpu_counters_unavailable")
            write(summary_path, summary)
            receipt_path = directory / "receipt.json"
            receipt = json.loads(receipt_path.read_text("utf-8"))
            receipt["joint"]["measurement"]["summary"] = digest(summary_path)
            write(receipt_path, receipt)
            inventory_path = directory / "evidence-inventory.json"
            inventory = json.loads(inventory_path.read_text("utf-8"))
            inventory["files"]["receipt.json"] = digest(receipt_path)
            inventory["files"]["joint-all-latest/measurements/summary.json"] = digest(summary_path)
            write(inventory_path, inventory)
            output = root / "aggregate"
            self.assertEqual(self.execute(candidate, cells, output, "422"), 1)
            matrix = json.loads((output / "matrix-receipt.json").read_text("utf-8"))
            self.assertEqual(
                matrix["counts"],
                {"failed": 1, "passed": 19, "running": 0},
                matrix["cells"][:2],
            )

    def test_aggregate_rejects_rebuilt_wheel_payload_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _candidate, document, candidate_hash = self.candidate(root, "420")
            cells = self.cells(root, document, candidate_hash, "420")
            cell = next(iter(self.aggregate.EXPECTED))
            directory = cells / f"universality-cell-{cell}-420-1"
            rebuild_path = directory / "sdist-rebuild/receipt.json"
            rebuild = json.loads(rebuild_path.read_text("utf-8"))
            rebuild["packages"]["core"]["rebuilt_identity"]["installed_payload_sha256"] = "f" * 64
            write(rebuild_path, rebuild)
            receipt_path = directory / "receipt.json"
            receipt = json.loads(receipt_path.read_text("utf-8"))
            receipt["sdist_rebuild"]["receipt_record"] = digest(rebuild_path)
            with self.assertRaisesRegex(ValueError, "identity or payload differs"):
                self.aggregate.verify_sdist_rebuild(directory, receipt, document)

    def test_aggregate_rejects_unhashed_rebuild_runtime_lock(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _candidate, document, candidate_hash = self.candidate(root, "421")
            cells = self.cells(root, document, candidate_hash, "421")
            cell = next(iter(self.aggregate.EXPECTED))
            directory = cells / f"universality-cell-{cell}-421-1"
            runtime_lock = directory / "sdist-rebuild/runtime.lock"
            runtime_lock.write_text("typing-extensions==4.15.0\n", "utf-8")
            rebuild_path = directory / "sdist-rebuild/receipt.json"
            rebuild = json.loads(rebuild_path.read_text("utf-8"))
            rebuild["installation"]["runtime_lock_record"] = digest(runtime_lock)
            write(rebuild_path, rebuild)
            receipt_path = directory / "receipt.json"
            receipt = json.loads(receipt_path.read_text("utf-8"))
            receipt["sdist_rebuild"]["receipt_record"] = digest(rebuild_path)
            with self.assertRaisesRegex(ValueError, "not exact and SHA-256 authenticated"):
                self.aggregate.verify_sdist_rebuild(directory, receipt, document)

    def test_aggregate_fails_closed_when_one_native_cell_is_absent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            candidate, document, candidate_hash = self.candidate(root, "43")
            cells = self.cells(root, document, candidate_hash, "43")
            missing = next(iter(self.aggregate.EXPECTED))
            shutil.rmtree(cells / f"universality-cell-{missing}-43-1")
            output = root / "aggregate"
            self.assertEqual(self.execute(candidate, cells, output, "43"), 1)
            receipt = json.loads((output / "matrix-receipt.json").read_text("utf-8"))
            self.assertEqual(receipt["status"], "failed")
            self.assertEqual(receipt["counts"]["failed"], 1)

    def test_aggregate_keeps_cell_diagnostics_when_matrix_job_failed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            candidate, document, candidate_hash = self.candidate(root, "44")
            cells = self.cells(root, document, candidate_hash, "44")
            output = root / "aggregate"
            self.assertEqual(
                self.execute(
                    candidate,
                    cells,
                    output,
                    "44",
                    matrix_result="failure",
                ),
                1,
            )
            receipt = json.loads((output / "matrix-receipt.json").read_text("utf-8"))
            self.assertEqual(receipt["status"], "failed")
            self.assertEqual(receipt["counts"]["passed"], 20)
            self.assertIn(
                {
                    "stage": "workflow_jobs",
                    "candidate": "success",
                    "native_matrix": "failure",
                },
                receipt["errors"],
            )

    def test_aggregate_rejects_a_file_absent_from_the_closed_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            candidate, document, candidate_hash = self.candidate(root, "45")
            cells = self.cells(root, document, candidate_hash, "45")
            cell = next(iter(self.aggregate.EXPECTED))
            directory = cells / f"universality-cell-{cell}-45-1"
            unexpected = directory / "not-part-of-the-compact-contract.txt"
            unexpected.write_text("unexpected\n", "utf-8")
            output = root / "aggregate"
            self.assertEqual(self.execute(candidate, cells, output, "45"), 1)
            receipt = json.loads((output / "matrix-receipt.json").read_text("utf-8"))
            self.assertEqual(receipt["counts"]["failed"], 1)

    def test_aggregate_does_not_mix_workflow_attempt_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            candidate, document, candidate_hash = self.candidate(root, "46", "2")
            cells = self.cells(root, document, candidate_hash, "46", "1")
            output = root / "aggregate"
            self.assertEqual(self.execute(candidate, cells, output, "46", "2"), 1)
            receipt = json.loads((output / "matrix-receipt.json").read_text("utf-8"))
            self.assertEqual(receipt["status"], "failed")
            self.assertEqual(receipt["counts"]["failed"], 20)
            self.assertTrue(receipt["errors"][0]["unexpected_cell_artifacts"])

    def test_aggregate_rejects_unoptimized_fault_checks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            candidate, document, candidate_hash = self.candidate(root, "47")
            cells = self.cells(root, document, candidate_hash, "47")
            cell = next(iter(self.aggregate.EXPECTED))
            directory = cells / f"universality-cell-{cell}-47-1"
            fault_path = directory / "joint-all-latest/consumer-faults/fault-checks.json"
            fault = json.loads(fault_path.read_text("utf-8"))
            fault["environment"]["optimized"] = 0
            write(fault_path, fault)
            receipt_path = directory / "receipt.json"
            receipt = json.loads(receipt_path.read_text("utf-8"))
            receipt["joint"]["consumer_faults"]["record"] = digest(fault_path)
            write(receipt_path, receipt)
            inventory_path = directory / "evidence-inventory.json"
            inventory = json.loads(inventory_path.read_text("utf-8"))
            inventory["files"]["receipt.json"] = digest(receipt_path)
            inventory["files"]["joint-all-latest/consumer-faults/fault-checks.json"] = digest(
                fault_path
            )
            write(inventory_path, inventory)
            output = root / "aggregate"
            self.assertEqual(self.execute(candidate, cells, output, "47"), 1)
            matrix = json.loads((output / "matrix-receipt.json").read_text("utf-8"))
            self.assertEqual(matrix["counts"]["failed"], 1)

    def test_joint_suites_require_the_frozen_test_denominators(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _candidate, document, candidate_hash = self.candidate(root, "471")
            cells = self.cells(root, document, candidate_hash, "471")
            cell = next(iter(self.aggregate.EXPECTED))
            directory = cells / f"universality-cell-{cell}-471-1"
            receipt = json.loads((directory / "receipt.json").read_text("utf-8"))
            self.aggregate.verify_joint(directory, receipt, document)

            for suite_name in ("benchmark_suite", "consumer_suite"):
                with self.subTest(suite=suite_name):
                    mutated = json.loads(json.dumps(receipt))
                    mutated["joint"][suite_name]["junit_identities_sha256"] = "0" * 64
                    with self.assertRaisesRegex(ValueError, "receipt is incomplete"):
                        self.aggregate.verify_joint(directory, mutated, document)

            mutated = json.loads(json.dumps(receipt))
            mutated["joint"]["benchmark_suite"]["tests"] -= 1
            with self.assertRaisesRegex(ValueError, "receipt is incomplete"):
                self.aggregate.verify_joint(directory, mutated, document)

    def test_consumer_summary_contract_rejects_count_and_case_drift(self) -> None:
        valid = self.consumer_summary("1.0")
        self.aggregate.verify_consumer_summary(valid, "1.0")
        ControllerDurabilityTests.runner.verify_consumer_summary(valid, "1.0")
        optimized = self.consumer_summary("1.0", optimized=True)
        self.aggregate.verify_consumer_summary(optimized, "1.0", optimized=True)
        ControllerDurabilityTests.runner.verify_consumer_summary(optimized, "1.0", optimized=True)
        with self.assertRaises((ValueError, RuntimeError)):
            self.aggregate.verify_consumer_summary(optimized, "1.0")
        with self.assertRaises((ValueError, RuntimeError)):
            ControllerDurabilityTests.runner.verify_consumer_summary(optimized, "1.0")
        optimized_without_native_flag = json.loads(json.dumps(optimized))
        optimized_without_native_flag["records"][0]["command"].remove("-O")
        with self.assertRaises((ValueError, RuntimeError)):
            self.aggregate.verify_consumer_summary(
                optimized_without_native_flag, "1.0", optimized=True
            )
        with self.assertRaises((ValueError, RuntimeError)):
            ControllerDurabilityTests.runner.verify_consumer_summary(
                optimized_without_native_flag, "1.0", optimized=True
            )
        mutations: tuple[tuple[str, Callable[[dict[str, Any]], None]], ...] = (
            (
                "native-attempt-count",
                lambda value: value.__setitem__("native_execution_attempts", 143),
            ),
            (
                "case-identity",
                lambda value: value["records"][71].__setitem__("program", "reconciliation"),
            ),
            (
                "unexpected-case-field",
                lambda value: value["records"][0].__setitem__("unverified", True),
            ),
            (
                "exit-code-type",
                lambda value: value["records"][1].__setitem__("actual_exit", True),
            ),
        )
        for label, mutate in mutations:
            with self.subTest(label=label):
                changed = json.loads(json.dumps(valid))
                mutate(changed)
                with self.assertRaises((ValueError, RuntimeError)):
                    self.aggregate.verify_consumer_summary(changed, "1.0")
                with self.assertRaises((ValueError, RuntimeError)):
                    ControllerDurabilityTests.runner.verify_consumer_summary(changed, "1.0")

    def test_measurement_contract_accepts_all_platforms_and_rejects_mutations(
        self,
    ) -> None:
        for requested in (
            {"system": "Linux", "architecture": "x64", "python": "3.10"},
            {"system": "Linux", "architecture": "arm64", "python": "3.11"},
            {"system": "Windows", "architecture": "x64", "python": "3.12"},
            {"system": "Darwin", "architecture": "x64", "python": "3.13"},
            {"system": "Darwin", "architecture": "arm64", "python": "3.10"},
        ):
            with self.subTest(valid=requested):
                protocol, summary, bounded = self.measurement_documents(requested)
                for verifier in (
                    self.aggregate.verify_measurement_documents,
                    ControllerDurabilityTests.runner.verify_measurement_documents,
                ):
                    verifier(
                        protocol,
                        summary,
                        bounded,
                        requested_system=requested["system"],
                        requested_architecture=requested["architecture"],
                        requested_python=requested["python"],
                    )

        requested = {"system": "Windows", "architecture": "x64", "python": "3.12"}

        def set_wrong_platform_reason(
            _protocol: dict[str, Any],
            summary: dict[str, Any],
            _bounded: dict[str, Any],
        ) -> None:
            summary["results"][0]["resource_measurement_contract"]["metrics"][5]["reason"] = (
                "generic_unavailable"
            )
            summary["results"][0]["process"]["metric_coverage"][5]["reason"] = "generic_unavailable"

        def set_unexpected_measurement_failure(
            _protocol: dict[str, Any],
            summary: dict[str, Any],
            _bounded: dict[str, Any],
        ) -> None:
            for metrics in (
                summary["results"][0]["resource_measurement_contract"]["metrics"],
                summary["results"][0]["process"]["metric_coverage"],
            ):
                metrics[0].update(
                    state="measurement_failed",
                    source=None,
                    reason="rss_observation_failed",
                )
            summary["results"][0]["process"]["sampled_rss_peak_bytes"] = None

        def remove_observed_source(
            _protocol: dict[str, Any],
            summary: dict[str, Any],
            _bounded: dict[str, Any],
        ) -> None:
            summary["results"][0]["resource_measurement_contract"]["metrics"][0]["source"] = None
            summary["results"][0]["process"]["metric_coverage"][0]["source"] = None

        mutations: tuple[
            tuple[
                str,
                Callable[[dict[str, Any], dict[str, Any], dict[str, Any]], None],
            ],
            ...,
        ] = (
            (
                "protocol-size",
                lambda protocol, _summary, _bounded: protocol["rows"].pop(),
            ),
            (
                "summary-protocol-drift",
                lambda _protocol, summary, _bounded: summary["protocol"].__setitem__("width", 3),
            ),
            (
                "missing-size",
                lambda _protocol, summary, _bounded: summary["results"].pop(),
            ),
            (
                "repetition-count",
                lambda _protocol, summary, _bounded: summary["results"][0].__setitem__(
                    "observed_repetitions", 2
                ),
            ),
            (
                "false-completion",
                lambda _protocol, summary, _bounded: summary["results"][0].__setitem__(
                    "resource_measurement_complete", False
                ),
            ),
            (
                "missing-observed-value",
                lambda _protocol, summary, _bounded: summary["results"][0]["process"].__setitem__(
                    "io_read_bytes", None
                ),
            ),
            ("missing-observed-source", remove_observed_source),
            ("unexpected-measurement-failure", set_unexpected_measurement_failure),
            (
                "wrong-platform-reason",
                set_wrong_platform_reason,
            ),
            (
                "monitoring-error",
                lambda _protocol, summary, _bounded: summary["results"][0]["process"][
                    "monitoring_errors"
                ].append("cpu_counters_unavailable"),
            ),
            (
                "accepted-limit",
                lambda _protocol, _summary, bounded: bounded.__setitem__("complete", True),
            ),
            (
                "wrong-limit-diagnostic",
                lambda _protocol, _summary, bounded: bounded["diagnostics"][0].__setitem__(
                    "code", "timeout"
                ),
            ),
        )
        for label, mutate in mutations:
            protocol, summary, bounded = self.measurement_documents(requested)
            mutate(protocol, summary, bounded)
            for verifier in (
                self.aggregate.verify_measurement_documents,
                ControllerDurabilityTests.runner.verify_measurement_documents,
            ):
                with (
                    self.subTest(mutation=label, verifier=verifier.__module__),
                    self.assertRaises((TypeError, ValueError, RuntimeError)),
                ):
                    verifier(
                        protocol,
                        summary,
                        bounded,
                        requested_system=requested["system"],
                        requested_architecture=requested["architecture"],
                        requested_python=requested["python"],
                    )

    def test_fault_contract_rejects_wrong_state_and_extra_fields(self) -> None:
        valid = {
            "status": "PASS",
            "environment": {"isolated": 1, "optimized": 1},
            "synthetic_fixture": True,
            "checks": [
                {
                    "case": "accept",
                    "state": "equivalent",
                    "accepted": True,
                    "error": None,
                },
                {
                    "case": "compensated_reject",
                    "state": "different",
                    "accepted": False,
                    "error": "EquivalenceAssertionError",
                },
                {
                    "case": "budget_reject",
                    "state": "not_evaluable",
                    "accepted": False,
                    "error": "EquivalenceAssertionError",
                },
                {
                    "case": "rejected_input",
                    "prior_publication_preserved": True,
                    "staging_clean": True,
                },
                {
                    "case": "write_fault",
                    "prior_publication_preserved": True,
                    "staging_clean": True,
                },
                {"case": "report_corruption", "rejected": True},
            ],
        }
        self.aggregate.verify_fault_checks(valid)
        ControllerDurabilityTests.runner.verify_fault_checks(valid)
        mutations: tuple[tuple[str, Callable[[dict[str, Any]], None]], ...] = (
            (
                "wrong-state",
                lambda value: value["checks"][1].__setitem__("state", "equivalent"),
            ),
            (
                "extra-field",
                lambda value: value["checks"][0].__setitem__("unchecked", True),
            ),
            (
                "boolean-type",
                lambda value: value["checks"][0].__setitem__("accepted", 1),
            ),
        )
        for label, mutate in mutations:
            with self.subTest(label=label):
                changed = json.loads(json.dumps(valid))
                mutate(changed)
                with self.assertRaises((ValueError, RuntimeError)):
                    self.aggregate.verify_fault_checks(changed)
                with self.assertRaises((ValueError, RuntimeError)):
                    ControllerDurabilityTests.runner.verify_fault_checks(changed)

    def test_h_summary_hash_is_bound_to_actual_bundle_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            bundle = Path(temporary) / "portable/bundle.json"
            write(bundle, {"closed_inventory": True})
            summary = {
                "journey": "H",
                "synthetic": True,
                "scenario": "good",
                "accepted": True,
                "exit_code": 0,
                "integrity": "passed",
                "report_created": True,
                "original_paths_available": False,
                "operational_state": "passed",
                "bundle_manifest_sha256": hashlib.sha256(bundle.read_bytes()).hexdigest(),
                "independent_review": "not_requested",
                "comparisons": [
                    {
                        "state": "equivalent",
                        "complete": True,
                        "counts_final": True,
                        "accepted": True,
                        "exit_code": 0,
                        "difference_records": 0,
                        "diagnostic_codes": [],
                        "report": f"reports/comparison-{index}/report.html",
                    }
                    for index in range(2)
                ],
            }
            self.aggregate.verify_h_summary(summary, "good", 0, bundle_manifest=bundle)
            ControllerDurabilityTests.runner.verify_h_summary(
                summary, "good", 0, bundle_manifest=bundle
            )
            write(bundle, {"closed_inventory": False})
            with self.assertRaisesRegex(ValueError, "bundle manifest bytes differ"):
                self.aggregate.verify_h_summary(summary, "good", 0, bundle_manifest=bundle)
            with self.assertRaisesRegex(RuntimeError, "bundle manifest bytes differ"):
                ControllerDurabilityTests.runner.verify_h_summary(
                    summary, "good", 0, bundle_manifest=bundle
                )

    def test_candidate_payload_comparison_binds_wheel_to_sdist_source(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            wheel = root / "demo.whl"
            with zipfile.ZipFile(wheel, "w") as archive:
                archive.writestr("demo/__init__.py", b"value = 1\n")
            sdist = root / "demo.tar.gz"
            raw = b"value = 1\n"
            with tarfile.open(sdist, "w:gz") as archive:
                member = tarfile.TarInfo("demo-1/src/demo/__init__.py")
                member.size = len(raw)
                archive.addfile(member, io.BytesIO(raw))
            observed = self.prepare.compare_runtime_payloads(wheel, sdist, "demo")
            self.assertEqual(observed["source_file_count"], 1)
            with zipfile.ZipFile(wheel, "w") as archive:
                archive.writestr("demo/__init__.py", b"value = 2\n")
            with self.assertRaisesRegex(ValueError, "payload differs"):
                self.prepare.compare_runtime_payloads(wheel, sdist, "demo")

    def test_candidate_test_manifest_binds_source_and_sdist_tests(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            test_file = source / "tests/test_demo.py"
            test_file.parent.mkdir(parents=True)
            test_file.write_text("def test_demo():\n    assert True\n", "utf-8")
            sdist = root / "demo.tar.gz"
            raw = test_file.read_bytes()
            with tarfile.open(sdist, "w:gz") as archive:
                member = tarfile.TarInfo("demo-1/tests/test_demo.py")
                member.size = len(raw)
                archive.addfile(member, io.BytesIO(raw))
            manifest = root / "manifest.json"
            write(
                manifest,
                {
                    "schema": "equiframe-test-manifest-1",
                    "package": "demo",
                    "pytest_version": "9.0.2",
                    "hypothesis_version": "6.142.4",
                    "plugin_autoload_disabled": True,
                    "files": self.prepare.source_test_inventory(source),
                    "tests": [
                        {
                            "nodeid": "tests/test_demo.py::test_demo",
                            "classname": "tests.test_demo",
                            "name": "test_demo",
                        }
                    ],
                    "test_count": 1,
                },
            )
            output = root / "candidate"
            output.mkdir()
            result = self.prepare.copy_test_manifest(
                manifest,
                package="demo",
                source=source,
                sdist=sdist,
                output=output,
            )
            self.assertEqual(result["test_count"], 1)
            test_file.write_text("def test_demo():\n    assert False\n", "utf-8")
            with self.assertRaisesRegex(ValueError, "differ"):
                self.prepare.copy_test_manifest(
                    manifest,
                    package="demo",
                    source=source,
                    sdist=sdist,
                    output=root / "second-candidate",
                )

    def test_candidate_paths_reject_cross_platform_collisions_and_reserved_names(
        self,
    ) -> None:
        with self.assertRaisesRegex(ValueError, "collision"):
            self.prepare.unique_portable_paths(
                [("root/A.txt", False), ("root/a.txt", False)], "fixture"
            )
        for path in ("root/CON.txt", "root/file:stream", "root/name. ", "root/.hidden"):
            with (
                self.subTest(path=path),
                self.assertRaisesRegex(ValueError, "nonportable"),
            ):
                self.prepare.portable_path(path)


if __name__ == "__main__":
    unittest.main()
