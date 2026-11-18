"""Synthetic tests for command semantics enforced by the VM receipt validator."""

from __future__ import annotations

import unittest

from validate_vm_receipts import (
    validate_benchmark_command_contract,
    validate_core_command_contract,
)


def core_command(*, missing: str | None = None) -> list[dict]:
    command = [
        "uv",
        "pip",
        "install",
        "--python",
        "/tmp/venv/bin/python",
        "--no-index",
        "--no-deps",
        "--reinstall",
        "candidate.whl",
    ]
    return [
        {
            "stage": "install-exact-wheel",
            "command": [argument for argument in command if argument != missing],
            "exit_code": 0,
        }
    ]


def benchmark_commands() -> list[dict]:
    return [
        {
            "label": "resolve",
            "command": [
                "uv",
                "pip",
                "compile",
                "runtime.in",
                "--generate-hashes",
                "--only-binary",
                ":all:",
            ],
            "exit_code": 0,
        },
        {
            "label": "dependencies",
            "command": [
                "uv",
                "pip",
                "sync",
                "--require-hashes",
                "--only-binary",
                ":all:",
                "runtime.lock",
            ],
            "exit_code": 0,
        },
    ]


class ReceiptCommandContractTests(unittest.TestCase):
    def test_core_receipt_proves_exact_wheel_reinstall_semantics(self):
        validate_core_command_contract(core_command())

    def test_core_exit_zero_cannot_hide_missing_exact_wheel_flags(self):
        for missing in ("--no-index", "--no-deps", "--reinstall"):
            with (
                self.subTest(missing=missing),
                self.assertRaisesRegex(ValueError, missing),
            ):
                validate_core_command_contract(core_command(missing=missing))

    def test_core_profile_rejects_ambiguous_exact_wheel_stage(self):
        command = core_command()[0]
        with self.assertRaisesRegex(ValueError, "exactly one"):
            validate_core_command_contract([command, command])

    def test_core_profile_rejects_an_index_despite_no_index_flag(self):
        commands = core_command()
        commands[0]["command"].extend(["--index-url", "https://example.invalid/simple"])
        with self.assertRaisesRegex(ValueError, "forbidden"):
            validate_core_command_contract(commands)

    def test_benchmark_receipt_proves_binary_hashed_solve_and_sync(self):
        validate_benchmark_command_contract(benchmark_commands())

    def test_benchmark_exit_zero_cannot_hide_source_capable_resolution(self):
        commands = benchmark_commands()
        commands[0]["command"].remove("--only-binary")
        with self.assertRaisesRegex(ValueError, "only-binary"):
            validate_benchmark_command_contract(commands)

    def test_benchmark_sync_requires_hashes_and_binary_only(self):
        for missing in ("--require-hashes", "--only-binary"):
            commands = benchmark_commands()
            commands[1]["command"].remove(missing)
            with (
                self.subTest(missing=missing),
                self.assertRaisesRegex(ValueError, missing),
            ):
                validate_benchmark_command_contract(commands)

    def test_benchmark_binary_policy_must_apply_to_all_artifacts(self):
        commands = benchmark_commands()
        commands[0]["command"][commands[0]["command"].index(":all:")] = ":none:"
        with self.assertRaisesRegex(ValueError, ":all:"):
            validate_benchmark_command_contract(commands)


if __name__ == "__main__":
    unittest.main()
