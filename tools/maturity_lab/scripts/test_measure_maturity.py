#!/usr/bin/env python3
"""Portable filesystem-observation tests; no benchmark claim or fabricated receipt."""

import platform
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from measure_maturity import (
    _observe_linux_filesystem,
    _observe_macos_filesystem,
    _observe_windows_filesystem,
    _windows_observation_from_details,
    observe_filesystem,
    validate_resource_contract,
)


class FilesystemObservationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def test_linux_uses_deepest_mount_and_preserves_method(self):
        measurement = self.root / "RAM area" / "measurement"
        measurement.mkdir(parents=True)
        encoded_root = str(self.root).replace("\\", r"\134").replace(" ", r"\040")
        encoded_ram = (
            str(measurement.parent).replace("\\", r"\134").replace(" ", r"\040")
        )
        mountinfo = self.root / "mountinfo"
        mountinfo.write_text(
            f"1 0 0:1 / {encoded_root} rw - overlay overlay rw\n"
            f"2 1 0:2 / {encoded_ram} rw - tmpfs tmpfs rw\n",
            encoding="utf-8",
        )
        observation = _observe_linux_filesystem(measurement, mountinfo=mountinfo)
        self.assertEqual(
            (observation.filesystem, observation.storage), ("tmpfs", "tmpfs")
        )
        self.assertEqual(observation.method, "linux_proc_self_mountinfo")
        self.assertEqual(Path(observation.mount_point), measurement.parent)
        self.assertTrue(observation.limitations)

    def test_linux_missing_or_unusable_mount_table_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, "Cannot observe"):
            _observe_linux_filesystem(self.root, mountinfo=self.root / "missing")
        mountinfo = self.root / "mountinfo"
        mountinfo.write_text("unusable mount row\n", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "not found"):
            _observe_linux_filesystem(self.root, mountinfo=mountinfo)

    def test_windows_fixed_and_ramdisk_drive_types_are_distinct(self):
        fixed = _windows_observation_from_details("NTFS", 3, "C:\\")
        self.assertEqual((fixed.storage, fixed.backing_kind), ("disk", "fixed"))
        self.assertEqual(fixed.method, "windows_get_volume_information_and_drive_type")
        self.assertTrue(fixed.limitations)

        ramdisk = _windows_observation_from_details("FAT32", 6, "R:\\")
        self.assertEqual((ramdisk.storage, ramdisk.backing_kind), ("tmpfs", "ramdisk"))

    def test_windows_remote_volume_is_recorded_without_calling_it_local(self):
        remote = _windows_observation_from_details("NTFS", 4, "\\\\server\\share\\")
        self.assertEqual(remote.storage, "disk")
        self.assertEqual(remote.backing_kind, "remote")
        self.assertTrue(any("remote" in item for item in remote.limitations))

    def test_windows_unknown_drive_or_empty_filesystem_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, "drive type"):
            _windows_observation_from_details("NTFS", 0, "C:\\")
        with self.assertRaisesRegex(RuntimeError, "filesystem type is empty"):
            _windows_observation_from_details(" ", 3, "C:\\")

    def test_windows_api_failure_fails_closed(self):
        with (
            patch(
                "measure_maturity._windows_volume_details",
                side_effect=PermissionError(),
            ),
            self.assertRaisesRegex(RuntimeError, "Cannot observe Windows"),
        ):
            _observe_windows_filesystem(self.root)

    @unittest.skipUnless(platform.system() == "Windows", "native Win32 volume APIs")
    def test_current_windows_volume_is_observed_natively(self):
        observation = observe_filesystem(self.root)
        self.assertEqual(
            observation.method, "windows_get_volume_information_and_drive_type"
        )
        self.assertIn(observation.storage, ("disk", "tmpfs"))
        self.assertTrue(observation.filesystem)
        self.assertTrue(observation.mount_point)
        self.assertTrue(observation.limitations)
        self.assertEqual(
            observation.record()["limitations"], list(observation.limitations)
        )

    def test_macos_uses_the_deepest_mount_and_decodes_escapes(self):
        measurement = self.root / "RAM area" / "measurement"
        measurement.mkdir(parents=True)
        encoded_root = str(self.root).replace(" ", r"\040")
        encoded_ram = str(measurement.parent).replace(" ", r"\040")
        mounts = (
            f"/dev/disk1 on {encoded_root} (apfs, local, journaled)\n"
            f"tmpfs on {encoded_ram} (tmpfs, local)\n"
        )
        observation = _observe_macos_filesystem(measurement, mount_output=mounts)
        self.assertEqual(observation.filesystem, "tmpfs")
        self.assertEqual(observation.storage, "tmpfs")
        self.assertEqual(observation.method, "macos_sbin_mount_table")
        self.assertEqual(Path(observation.mount_point), measurement.parent)
        self.assertTrue(observation.limitations)

    def test_macos_unusable_mount_output_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, "not found"):
            _observe_macos_filesystem(self.root, mount_output="unusable mount row\n")

    def test_missing_directory_and_unknown_platform_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "must exist"):
            observe_filesystem(self.root / "missing", system="Windows")
        with self.assertRaisesRegex(RuntimeError, "Unsupported operating system"):
            observe_filesystem(self.root, system="Plan9")

    def test_summary_resource_contract_must_match_and_enumerate_metrics(self):
        summary = {
            "resource_measurement_contract": {
                "id": "equiframe_process_resources_v1",
                "platform": "windows",
                "metrics": [{"metric": "sampled_rss_peak_bytes"}],
            }
        }
        validate_resource_contract(
            summary,
            contract_id="equiframe_process_resources_v1",
            measurement_platform="windows",
        )
        for changed in (
            {},
            {"id": "legacy_unspecified", "platform": "windows", "metrics": [{}]},
            {
                "id": "equiframe_process_resources_v1",
                "platform": "linux",
                "metrics": [{}],
            },
            {
                "id": "equiframe_process_resources_v1",
                "platform": "windows",
                "metrics": [],
            },
        ):
            with (
                self.subTest(changed=changed),
                self.assertRaises((TypeError, ValueError)),
            ):
                validate_resource_contract(
                    {"resource_measurement_contract": changed},
                    contract_id="equiframe_process_resources_v1",
                    measurement_platform="windows",
                )


if __name__ == "__main__":
    unittest.main()
