#!/usr/bin/env python3
"""Review returned VM evidence against the exact kit; hashes cannot authenticate an operator."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def member(root: Path, name: str) -> Path:
    relative = Path(name)
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        raise ValueError("expected a relative evidence member")
    path = root / relative
    if any(
        (root / Path(*relative.parts[:n])).is_symlink() for n in range(1, len(relative.parts) + 1)
    ):
        raise ValueError("linked evidence member")
    if not path.resolve().is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError("receipt member missing or outside the evidence root")
    return path


class Review:
    def __init__(self, kit: Path, evidence: Path):
        self.kit, self.evidence = kit, evidence
        self.candidate = json.loads(member(kit, "candidate.json").read_text("utf-8"))
        if self.candidate.get("schema") != "equiframe-maturity-candidate-1":
            raise ValueError("unsupported candidate schema")
        for name, record in self.candidate["files"].items():
            path = member(kit, name)
            if sha(path) != record["sha256"] or path.stat().st_size != record["size_bytes"]:
                raise ValueError("candidate kit changed: " + name)
        self.receipt = json.loads(member(evidence, "receipt.json").read_text("utf-8"))
        self.inventory = json.loads(member(evidence, "evidence-inventory.json").read_text("utf-8"))[
            "files"
        ]
        if "receipt.json" not in self.inventory:
            raise ValueError("the top receipt is absent from its inventory")
        for name in self.inventory:
            self.file(name)
        self.lab = Path(self.receipt["lab"])
        self.wheel_payloads = {}
        for key, module in [
            ("core_wheel", "equiframe"),
            ("benchmark_wheel", "equiframe_benchmark"),
            ("consumer_wheel", "equiframe_consumer_lab"),
        ]:
            wheel = member(kit, self.candidate["artifacts"][key])
            if sha(wheel) != self.candidate["artifact_hashes"][key]:
                raise ValueError("candidate artifact and file manifest disagree")
            with zipfile.ZipFile(wheel) as archive:
                self.wheel_payloads[module] = {
                    name: {
                        "sha256": hashlib.sha256(archive.read(name)).hexdigest(),
                        "size_bytes": len(archive.read(name)),
                    }
                    for name in archive.namelist()
                    if name.startswith(module + "/") and not name.endswith("/")
                }

    def relative(self, original: str) -> str:
        path = Path(original)
        return path.relative_to(self.lab).as_posix() if path.is_absolute() else path.as_posix()

    def file(self, name: str, digest: str | None = None) -> Path:
        if name not in self.inventory:
            raise ValueError("required evidence is not inventoried: " + name)
        path = member(self.evidence, name)
        expected = self.inventory[name]
        actual = sha(path)
        if actual != expected["sha256"] or path.stat().st_size != expected["size_bytes"]:
            raise ValueError("evidence differs from its inventory: " + name)
        if digest is not None and actual != digest:
            raise ValueError("receipt digest differs from actual evidence: " + name)
        return path

    def json(self, name: str, digest: str | None = None) -> dict:
        return json.loads(self.file(name, digest).read_text("utf-8"))

    def commands(self, commands: list[dict], required: set[str], base: str = "") -> None:
        labels = [entry["label"] for entry in commands]
        if len(labels) != len(set(labels)) or not required <= set(labels):
            raise ValueError("required command stages are missing or repeated")
        for entry in commands:
            if entry.get("status") != "passed" or entry.get("exit_code") != entry.get(
                "expected_exit"
            ):
                raise ValueError("failed/timed-out command cannot be counted as passing")
            self.file((Path(base) / entry["log"]).as_posix(), entry["log_sha256"])

    def junit(self, path: str, minimum: int) -> None:
        root = ET.parse(self.file(path)).getroot()
        if root.tag not in ("testsuite", "testsuites"):
            raise ValueError("unrecognized JUnit document")
        cases = list(root.iter("testcase"))
        if len(cases) < minimum or any(
            case.find(tag) is not None for case in cases for tag in ("failure", "error", "skipped")
        ):
            raise ValueError("required suite is incomplete, failed, skipped or xfailed")
        for suite in root.iter("testsuite"):
            if int(suite.attrib.get("tests", "-1")) != len(list(suite.iter("testcase"))):
                raise ValueError("JUnit testcase count does not match its declaration")

    def pair_binding(self, path: str, minor: str) -> None:
        binding = self.json(path)
        if (
            not binding["python"].startswith(minor + ".")
            or binding["machine"] != "aarch64"
            or binding["isolated"] is not True
        ):
            raise ValueError("paired runtime is not the required actual isolated ARM64 Python")
        if set(binding["packages"]) != set(self.wheel_payloads):
            raise ValueError("paired runtime is missing a package binding")
        for module, item in binding["packages"].items():
            key = {
                "equiframe": "core_wheel",
                "equiframe_benchmark": "benchmark_wheel",
                "equiframe_consumer_lab": "consumer_wheel",
            }[module]
            if (
                item.get("verified") is not True
                or item["wheel_sha256"] != self.candidate["artifact_hashes"][key]
            ):
                raise ValueError("paired runtime wheel differs")
            if item["payload"] != {
                name: record["sha256"] for name, record in self.wheel_payloads[module].items()
            }:
                raise ValueError("paired runtime payload differs from the delivered wheel")

    def core_profile(self, profile: dict, minor: str) -> None:
        matrix = self.json(profile["matrix"], profile["matrix_sha256"])
        if (
            profile["status"] != "passed"
            or matrix.get("status") != "passed"
            or len(matrix["cells"]) != 1
        ):
            raise ValueError("core matrix cell did not pass")
        for item, key in [("wheel", "core_wheel"), ("sdist", "core_sdist")]:
            if matrix["artifacts"][item]["sha256"] != self.candidate["artifact_hashes"][key]:
                raise ValueError("core matrix used different artifact bytes")
        outer = matrix["cells"][0]
        if outer["status"] != "passed" or (outer["profile"], outer["endpoint"]) != (
            profile["profile"],
            profile["endpoint"],
        ):
            raise ValueError("core matrix and cell labels differ")
        name = self.relative(outer["receipt"])
        inner = self.json(name, outer["receipt_artifact"]["sha256"])
        if (
            inner["status"] != "passed"
            or inner.get("skips")
            or inner.get("blockers")
            or inner.get("error")
        ):
            raise ValueError("core inner receipt is not a clean pass")
        if (
            inner["interpreter"]["python_version"] != minor
            or inner["interpreter"]["platform_machine"] != "aarch64"
        ):
            raise ValueError("core cell interpreter differs from claimed VM cell")
        if (
            inner["runtime_binding"]["files"] != self.wheel_payloads["equiframe"]
            or inner["runtime_binding"]["verified"] is not True
        ):
            raise ValueError("core installed payload differs from candidate")
        if (
            not inner["runtime_binding"]["python"].startswith(minor + ".")
            or inner["runtime_binding"]["machine"] != "aarch64"
        ):
            raise ValueError("installed runtime differs from interpreter probe")
        stages = {item["stage"] for item in inner["commands"]}
        needed = {
            "interpreter",
            "resolve-runtime",
            "create-clean-venv",
            "sync-runtime",
            "install-exact-wheel",
            "runtime-pip-check",
            "public-api",
            "binding-after",
        }
        needed.update({"cli-help", "cli-invalid-contract"})
        needed.update(
            "cli-contract-" + name
            for name in ("aggregations", "dates", "duplicates_order", "joins", "nulls_types")
        )
        selected = profile["profile"]
        if selected not in ("base", "ml"):
            needed.update(
                "cli-compare-" + state for state in ("equivalent", "different", "not_evaluable")
            )
            engines = (
                ("pandas", "polars", "duckdb")
                if selected in ("engines", "all")
                else ((selected,) if selected in ("pandas", "polars", "duckdb") else ())
            )
            for engine in ("arrow", *engines):
                needed.update(
                    f"assertion-{engine}-{state}"
                    for state in ("equivalent", "different", "not_evaluable")
                )
            needed.update("native-execution-" + engine for engine in engines)
        if selected in ("ml", "all"):
            needed.add("ml-fit-calibrate-detect")
        if selected in ("duckdb", "engines", "all"):
            needed.add("duckdb-detached-capture")
        if selected in ("engines", "all"):
            needed.add("native-migration-six-directions")
        if not needed <= stages:
            raise ValueError("core profile omitted a required stage")
        lock = self.file(str(Path(name).parent / "runtime.lock"), inner["runtime_lock"]["sha256"])
        pins = dict(re.findall(r"^([A-Za-z0-9_.-]+)==([^\s;]+)", lock.read_text("utf-8"), re.M))
        normalized = {key.lower().replace("_", "-"): value for key, value in pins.items()}
        if not normalized or normalized != inner["runtime_versions"]:
            raise ValueError("core dependency inventory differs from actual lock")
        if any(
            inner["runtime_binding"]["versions"].get(key) != version
            for key, version in normalized.items()
        ):
            raise ValueError("core runtime dependencies differ from lock")
        for command in inner["commands"]:
            stage = command["stage"]
            expected = (
                2
                if stage == "cli-invalid-contract"
                else (
                    1
                    if stage.startswith(("cli-compare-", "assertion-"))
                    and stage.endswith("-different")
                    else 3
                    if stage.startswith(("cli-compare-", "assertion-"))
                    and stage.endswith("-not_evaluable")
                    else 0
                )
            )
            if command.get("expected_exit_code") != expected:
                raise ValueError("core stage changed its independent expected exit")
            if command.get("exit_code") != command.get("expected_exit_code"):
                raise ValueError("core command failed or timed out")
            for stream in ("stdout", "stderr"):
                self.file(self.relative(command[stream]), command[stream + "_artifact"]["sha256"])
        if profile["profile"] == "all":
            if "full-installed-suite" not in stages or inner["suite"].get("accepted") is not True:
                raise ValueError("all-profile suite not fully accepted")
            self.junit(
                str(Path(name).parent / "pytest.xml"), self.candidate["suite_minimums"]["core"]
            )

    def benchmark_profile(self, profile: dict, minor: str) -> None:
        path = profile["receipt"]
        inner = self.json(path, profile["receipt_sha256"])
        if inner.get("status") != "passed" or inner.get("errors"):
            raise ValueError("benchmark isolated profile did not pass")
        if (inner["profile"], inner["endpoint"]) != (profile["profile"], profile["endpoint"]):
            raise ValueError("benchmark profile identity mismatch")
        for key in ("core_wheel", "benchmark_wheel"):
            if inner["artifacts"][key] != self.candidate["artifact_hashes"][key]:
                raise ValueError("benchmark profile installed another candidate")
        if (
            inner["interpreter"]["python_version"] != minor
            or inner["interpreter"]["platform_machine"] != "aarch64"
        ):
            raise ValueError("benchmark profile used another Python/platform")
        needed = {
            "interpreter",
            "resolve",
            "venv",
            "dependencies",
            "install-wheels",
            "pip-check",
            "binding",
            "cli-help",
            "optional-boundary",
        }
        if profile["profile"] in ("engines", "all"):
            needed.add("native-pilot")
        self.commands(inner["commands"], needed, str(Path(path).parent))
        binding = self.json(
            str(Path(path).parent / "runtime-binding.json"), inner["runtime_binding_sha256"]
        )
        lock = self.file(str(Path(path).parent / "runtime.lock"), inner["runtime_lock_sha256"])
        pins = dict(re.findall(r"^([A-Za-z0-9_.-]+)==([^\s;]+)", lock.read_text("utf-8"), re.M))
        installed = {
            key.lower().replace("_", "-"): version
            for key, version in binding["installed_distributions"].items()
        }
        if not pins or any(
            installed.get(key.lower().replace("_", "-")) != version for key, version in pins.items()
        ):
            raise ValueError("benchmark installed dependencies differ from lock")
        for module in ("equiframe", "equiframe_benchmark"):
            if binding["packages"][module]["payload"] != {
                name: item["sha256"] for name, item in self.wheel_payloads[module].items()
            }:
                raise ValueError("benchmark profile payload differs")

    def consumer_case(
        self,
        path: str,
        minor: str,
        program: str,
        variant: str,
        source: str,
        target: str,
        *,
        optimized: bool = False,
    ) -> dict:
        case = self.json(path)
        expected = {"good": 0, "defect": 1, "not_evaluable": 3}[variant]
        if (
            case.get("program"),
            case.get("variant"),
            case.get("direction"),
            case.get("observed_exit_code"),
            case.get("expected_exit_code"),
        ) != (program, variant, source + "->" + target, expected, expected):
            raise ValueError("consumer case identity or independent expected exit differs")
        if case.get("status") != ("PASS" if variant == "good" else "EXPECTED_REJECTION"):
            raise ValueError("consumer case did not observe the required verdict")
        if case.get("accepted") is not (variant == "good") or case.get("published") is not (
            variant == "good"
        ):
            raise ValueError("consumer acceptance/publication differs from independent expectation")
        if (
            case.get("evidence_integrity_verified") is not True
            or case.get("portable_verified_without_native_origin") is not True
            or case.get("frozen_data_unchanged") is not True
            or case.get("native_execution_count_complete") is not True
        ):
            raise ValueError("consumer integrity, portability or native coverage missing")
        expected_data = self.candidate["files"]["consumer-data/manifest.json"]["sha256"]
        if case.get("dataset_manifest_sha256") != expected_data:
            raise ValueError("consumer used a different frozen dataset")
        executions = case["native_result"]["executions"]
        if len(executions) != 2 or {item["engine"] for item in executions} != {source, target}:
            raise ValueError("consumer must retain both independent native executions")
        env = case["environment"]
        if (
            not env["python"].startswith(minor + ".")
            or env["machine"] != "aarch64"
            or env["isolated"] != 1
        ):
            raise ValueError("consumer execution has the wrong Python/platform/isolation")
        if optimized and env.get("optimized") != 1:
            raise ValueError("required optimized consumer execution was not observed")
        return case

    def validate(self) -> dict:
        receipt, candidate = self.receipt, self.candidate
        if receipt.get("schema") != "equiframe-maturity-vm-execution-1":
            raise ValueError("unknown VM receipt format")
        if receipt.get("cloud_validation_only") is not False:
            raise ValueError("cloud validation is not evidence of the required ARM64 VM")
        if receipt.get("candidate_manifest_sha256") != sha(self.kit / "candidate.json"):
            raise ValueError("VM receipt belongs to another candidate manifest")
        if (
            receipt.get("source") != candidate["source"]
            or receipt.get("artifact_hashes") != candidate["artifact_hashes"]
        ):
            raise ValueError("VM source/artifact identity differs")
        host = receipt["actual_host"]
        if (host["hostname"], host["user"], host["uid"], host["system"], host["machine"]) != (
            "maestria-vnic",
            "hernan",
            1003,
            "Linux",
            "aarch64",
        ):
            raise ValueError("receipt does not identify the required VM")
        if (
            not receipt.get("executor_declared")
            or receipt.get("status") != "passed"
            or receipt.get("errors")
        ):
            raise ValueError("VM execution incomplete, failed or executor unrecorded")
        required = {"controller-venv", "controller-pip", "controller-tools"}
        for minor in ("3.10", "3.12"):
            required.update(
                prefix + minor
                for prefix in (
                    "python-",
                    "all-pip-",
                    "pip-upgrade-",
                    "install-pair-consumer-",
                    "pair-pip-check-",
                    "benchmark-suite-",
                    "consumer-suite-",
                    "measure-bounded-",
                    "consumer-",
                    "consumer-recovery-",
                    "pair-binding-",
                    "sdist-venv-",
                    "sdist-pip-",
                    "sdist-pip-upgrade-",
                    "sdist-install-",
                    "sdist-pip-check-",
                    "sdist-consumer-",
                    "sdist-binding-",
                )
            )
            required.update(
                "optimized-H-" + minor + "-" + case
                for case in ("good", "different", "not_evaluable", "error")
            )
            required.update(
                "sdist-native-" + minor + "-" + variant
                for variant in ("good", "defect", "not_evaluable")
            )
            required.update(
                "sdist-build-" + name + "-" + minor for name in ("core", "benchmark", "consumer")
            )
        self.commands(receipt["commands"], required)
        outcomes = {"good": 0, "different": 1, "not_evaluable": 3, "error": 2}
        for command in receipt["commands"]:
            if command["label"].startswith("optimized-H-"):
                expected = outcomes[command["label"].split("-", 3)[-1]]
            elif command["label"].startswith("sdist-native-"):
                expected = {"good": 0, "defect": 1, "not_evaluable": 3}[
                    command["label"].split("-", 3)[-1]
                ]
            else:
                expected = 0
            if command["expected_exit"] != expected:
                raise ValueError("command changed the independent expected exit")
        cells = receipt["python_cells"]
        if len(cells) != 2 or {cell["minor"] for cell in cells} != {"3.10", "3.12"}:
            raise ValueError("both Python minors are required exactly once")
        for cell in cells:
            minor = cell["minor"]
            if (
                cell.get("status") != "passed"
                or cell.get("errors")
                or cell.get("sdist_verified") is not True
            ):
                raise ValueError("Python cell incomplete")
            if (
                not cell["interpreter"]["python"].startswith(minor + ".")
                or cell["interpreter"]["machine"] != "aarch64"
            ):
                raise ValueError("actual Python/architecture differs")
            for key, names, function in [
                (
                    "profiles",
                    ("base", "arrow", "pandas", "polars", "duckdb", "engines", "ml", "all"),
                    self.core_profile,
                ),
                (
                    "benchmark_profiles",
                    ("base", "engines", "ml", "resources", "all"),
                    self.benchmark_profile,
                ),
            ]:
                wanted = {(name, endpoint) for name in names for endpoint in ("minimum", "latest")}
                actual = [(item["profile"], item["endpoint"]) for item in cell[key]]
                if len(actual) != len(wanted) or set(actual) != wanted:
                    raise ValueError("required profile cells are missing/repeated")
                for item in cell[key]:
                    function(item, minor)
            root = f"py{minor}-all-latest/python-1-all-latest"
            self.junit(root + "/benchmark-junit.xml", candidate["suite_minimums"]["benchmark"])
            self.junit(root + "/consumer-junit.xml", candidate["suite_minimums"]["consumer"])
            constraints = self.file(
                root + "/pair-constraints.txt", cell["paired_runtime_constraints_sha256"]
            )
            core_cell = self.json(root + "/receipt.json")
            expected_pins = (
                "\n".join(
                    f"{name}=={version}"
                    for name, version in sorted(core_cell["runtime_versions"].items())
                )
                + "\n"
            )
            if constraints.read_text("utf-8") != expected_pins:
                raise ValueError("paired install constraints differ from the solved core runtime")
            for name in ("pair-binding.json", "sdist-binding.json"):
                self.pair_binding(root + "/" + name, minor)
                installed = self.json(root + "/" + name)["installed_distributions"]
                normalized = {
                    key.lower().replace("_", "-"): value for key, value in installed.items()
                }
                if any(
                    normalized.get(key) != value
                    for key, value in core_cell["runtime_versions"].items()
                ):
                    raise ValueError("paired wheel/sdist runtime changed a locked core dependency")
            sdist_cases = cell["sdist_consumer_cases"]
            if len(sdist_cases) != 3 or {case["variant"] for case in sdist_cases} != {
                "good",
                "defect",
                "not_evaluable",
            }:
                raise ValueError("sdist native journey missing a required outcome")
            for case in sdist_cases:
                self.file(case["receipt"], case["sha256"])
                self.consumer_case(
                    case["receipt"],
                    minor,
                    "reconciliation",
                    case["variant"],
                    "pandas",
                    "duckdb",
                    optimized=True,
                )
            for name in ("core", "benchmark", "consumer"):
                rebuild = cell["sdist_rebuilds"][name]
                if (
                    rebuild["wheel_sha256"] != candidate["artifact_hashes"][name + "_wheel"]
                    or rebuild["sdist_sha256"] != candidate["artifact_hashes"][name + "_sdist"]
                ):
                    raise ValueError("sdist rebuild byte identity differs")
            consumer = cell["consumer"]
            summary = self.json(consumer["summary"], consumer["sha256"])
            if (
                summary.get("status"),
                summary.get("distinct_cases"),
                summary.get("accepted_cases"),
                summary.get("rejected_cases"),
                summary.get("all_expected_outcomes_observed"),
                summary.get("recorded_native_executions"),
                summary.get("cases_with_unavailable_native_count"),
            ) != ("PASS", 72, 24, 48, True, 144, 0):
                raise ValueError("consumer actual/expected native outcomes incomplete")
            wanted = {
                (program, variant, source, target)
                for program in ("reconciliation", "refactor", "migration", "preparation")
                for source, target in itertools.permutations(("pandas", "polars", "duckdb"), 2)
                for variant in ("good", "defect", "not_evaluable")
            }
            records = summary["records"]
            observed = [
                (item["program"], item["variant"], item["source"], item["target"])
                for item in records
            ]
            if len(observed) != 72 or set(observed) != wanted:
                raise ValueError(
                    "72 consumer records are missing, repeated or outside the frozen matrix"
                )
            base = Path(consumer["summary"]).parent
            for item in records:
                expected = {"good": 0, "defect": 1, "not_evaluable": 3}[item["variant"]]
                if (
                    item.get("harness_pass") is not True
                    or item.get("process_outcome") != "completed"
                    or item.get("expected_exit") != expected
                    or item.get("actual_exit") != expected
                    or any(
                        item.get(key) is not None
                        for key in ("process_error", "receipt_error", "logs_error")
                    )
                ):
                    raise ValueError("consumer child process failed or changed its expected exit")
                for stream in ("stdout", "stderr"):
                    self.file(str(base / "logs" / (item["case_id"] + "." + stream + ".txt")))
                self.consumer_case(
                    str(base / item["case_receipt"]),
                    minor,
                    item["program"],
                    item["variant"],
                    item["source"],
                    item["target"],
                )
        return {
            "technical_receipts_consistent": True,
            "criteria_automatically_closed": [],
            "operator_authenticated_by_hashes": False,
            "independent_human_acceptance": False,
            "review_required": (
                "Confirm actual executor/transport provenance and review logs before closing M13"
            ),
            "source": candidate["source"],
            "candidate_manifest_sha256": sha(self.kit / "candidate.json"),
        }


def validate(kit: Path, evidence: Path) -> dict:
    return Review(kit, evidence).validate()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kit", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("choose a new review output; preserve earlier results")
    try:
        result, code = validate(args.kit.resolve(), args.evidence.resolve()), 0
    except Exception as error:
        result = {
            "technical_receipts_consistent": False,
            "error": type(error).__name__,
            "reason": str(error),
            "criteria_automatically_closed": [],
        }
        code = 1
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
