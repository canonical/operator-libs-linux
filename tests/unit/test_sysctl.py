# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

import tempfile
import unittest
from pathlib import Path
from subprocess import CalledProcessError
from unittest.mock import patch

from charms.operator_libs_linux.v0 import sysctl

permission_failure_output = """sysctl: permission denied on key "vm.swappiness", ignoring"""
partial_permission_failure_output = """sysctl: permission denied on key "vm.swappiness", ignoring
net.ipv4.tcp_max_syn_backlog = 4096
"""

TEST_OTHER_CHARM_FILE = """# othercharm
vm.swappiness=60
net.ipv4.tcp_max_syn_backlog=4096
"""
TEST_OTHER_CHARM_MERGED = f"""# This config file was produced by sysctl lib v{sysctl.LIBAPI}.{sysctl.LIBPATCH}
#
# This file represents the output of the sysctl lib, which can combine multiple
# configurations into a single file like.
# othercharm
vm.swappiness=60
net.ipv4.tcp_max_syn_backlog=4096
"""
TEST_MERGED_FILE = f"""# This config file was produced by sysctl lib v{sysctl.LIBAPI}.{sysctl.LIBPATCH}
#
# This file represents the output of the sysctl lib, which can combine multiple
# configurations into a single file like.
vm.max_map_count = 262144
vm.swappiness=0

"""
TEST_UPDATE_MERGED_FILE = f"""# This config file was produced by sysctl lib v{sysctl.LIBAPI}.{sysctl.LIBPATCH}
#
# This file represents the output of the sysctl lib, which can combine multiple
# configurations into a single file like.
# test
vm.max_map_count=25500
"""


def check_output_side_effects(*args, **kwargs):
    if args[0] == ["sysctl", "-n", "vm.swappiness"]:
        return "1"
    if args[0] == ["sysctl", "-n", "vm.swappiness", "other_value"]:
        return "1\n5"
    elif args[0] == ["sysctl", "vm.swappiness=1", "other_value=5"]:
        return "1\n5"
    elif args[0] == ["sysctl", "vm.swappiness=0"]:
        return permission_failure_output
    elif args[0] == ["sysctl", "vm.swappiness=0", "net.ipv4.tcp_max_syn_backlog=4096"]:
        return partial_permission_failure_output
    elif args[0] == ["sysctl", "exception"]:
        raise CalledProcessError(returncode=1, cmd=args[0], output="error on command")

    # Tests on 'update()'
    elif args[0] == ["sysctl", "-n", "vm.max_map_count"]:
        return "25000"
    elif args[0] == ["sysctl", "vm.max_map_count=25500"]:
        return "25500"


class TestSysctlConfig(unittest.TestCase):
    def setUp(self) -> None:
        tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_dir = Path(tmp_dir.name)
        self.addCleanup(tmp_dir.cleanup)

        # configured paths
        sysctl.SYSCTL_DIRECTORY = self.tmp_dir
        sysctl.SYSCTL_FILENAME = self.tmp_dir / "95-juju-sysctl.conf"

        self.loaded_values = {"vm.swappiness": "60", "vm.max_map_count": "25500"}

    @patch("charms.operator_libs_linux.v0.sysctl.check_output")
    def test_update_new_values(self, mock_output):
        mock_output.side_effect = check_output_side_effects
        config = sysctl.Config("test")

        config.configure({"vm.max_map_count": "25500"})

        self.assertEqual(config._desired_config, {"vm.max_map_count": "25500"})
        with open(self.tmp_dir / "95-juju-sysctl.conf", "r") as f:
            assert f.read() == TEST_UPDATE_MERGED_FILE

    @patch("charms.operator_libs_linux.v0.sysctl.Config._load_data")
    def test_update_with_validation_error(self, mock_load):
        mock_load.return_value = self.loaded_values
        config = sysctl.Config("test")

        with self.assertRaises(sysctl.ValidationError) as e:
            config.configure({"vm.max_map_count": "25000"})

        self.assertEqual(e.exception.message, "Validation error for keys: ['vm.max_map_count']")

    def test_update_with_permission_error(self):
        config = sysctl.Config("test")

        with self.assertRaises(sysctl.ApplyError) as e:
            config.configure({"vm.swappiness": "0", "net.ipv4.tcp_max_syn_backlog": "4096"})

        self.assertEqual(e.exception.message, "Unable to set params: ['vm.swappiness']")

    @patch("pathlib.Path.unlink")
    @patch("charms.operator_libs_linux.v0.sysctl.Config._merge")
    @patch("charms.operator_libs_linux.v0.sysctl.Config._load_data")
    def test_remove(self, mock_load, mock_merge, mock_unlink):
        mock_load.return_value = self.loaded_values
        config = sysctl.Config("test")

        config.remove()

        mock_unlink.assert_called()
        mock_merge.assert_called()

    def test_load_data(self):
        with open(self.tmp_dir / "95-juju-sysctl.conf", "w") as f:
            f.write(TEST_MERGED_FILE)

        config = sysctl.Config(name="test")

        assert config._data == {"vm.swappiness": "0", "vm.max_map_count": "262144"}

    def test_load_data_no_path(self):
        config = sysctl.Config(name="test")

        assert len(config) == 0

    @patch("charms.operator_libs_linux.v0.sysctl.Config._load_data")
    def test_merge(self, mock_load):
        mock_load.return_value = self.loaded_values
        config = sysctl.Config("test")
        with open(self.tmp_dir / "90-juju-othercharm", "w") as f:
            f.write(TEST_OTHER_CHARM_FILE)

        config._merge()

        assert (self.tmp_dir / "95-juju-sysctl.conf").exists
        with open(self.tmp_dir / "95-juju-sysctl.conf", "r") as f:
            assert f.read() == TEST_OTHER_CHARM_MERGED

    @patch("charms.operator_libs_linux.v0.sysctl.Config._load_data")
    def test_merge_without_own_file(self, mock_load):
        mock_load.return_value = self.loaded_values
        config = sysctl.Config("test")

        with open(self.tmp_dir / "90-juju-test", "w") as f:
            f.write("# test\nvalue=1\n")
        with open(self.tmp_dir / "90-juju-othercharm", "w") as f:
            f.write(TEST_OTHER_CHARM_FILE)

        config._merge(add_own_charm=False)

        assert (self.tmp_dir / "95-juju-sysctl.conf").exists
        with open(self.tmp_dir / "95-juju-sysctl.conf", "r") as f:
            assert f.read() == TEST_OTHER_CHARM_MERGED

    @patch("charms.operator_libs_linux.v0.sysctl.Config._load_data")
    def test_validate_different_keys(self, mock_load):
        mock_load.return_value = self.loaded_values
        config = sysctl.Config("test")

        config._desired_config = {"non_conflicting": "0"}
        result = config._validate()

        assert result == []

    @patch("charms.operator_libs_linux.v0.sysctl.Config._load_data")
    def test_validate_same_keys_and_values(self, mock_load):
        mock_load.return_value = self.loaded_values
        config = sysctl.Config("test")

        config._desired_config = {"vm.swappiness": "60"}
        result = config._validate()

        assert result == []

    @patch("charms.operator_libs_linux.v0.sysctl.Config._load_data")
    def test_validate_same_keys_different_values(self, mock_load):
        mock_load.return_value = self.loaded_values
        config = sysctl.Config("test")

        config._desired_config = {"vm.swappiness": "1"}
        result = config._validate()

        assert result == ["vm.swappiness"]

    def test_create_charm_file(self):
        config = sysctl.Config("test")

        config._desired_config = {"vm.swappiness": "0", "other_value": "10"}
        config._create_charm_file()

        with open(self.tmp_dir / "90-juju-test", "r") as f:
            assert f.read() == "# test\nvm.swappiness=0\nother_value=10\n"

    @patch("charms.operator_libs_linux.v0.sysctl.check_output")
    @patch("charms.operator_libs_linux.v0.sysctl.Config._load_data")
    def test_create_snapshot(self, mock_load, mock_output):
        mock_load.return_value = self.loaded_values
        mock_output.side_effect = check_output_side_effects
        config = sysctl.Config("test")

        config._desired_config = {"vm.swappiness": "0", "other_value": "10"}
        snapshot = config._create_snapshot()

        mock_output.assert_called_once_with(
            ["sysctl", "-n", "vm.swappiness", "other_value"], stderr=-2, universal_newlines=True
        )
        assert snapshot == {"vm.swappiness": "1", "other_value": "5"}

    @patch("charms.operator_libs_linux.v0.sysctl.check_output")
    @patch("charms.operator_libs_linux.v0.sysctl.Config._load_data")
    def test_restore_snapshot(self, mock_load, mock_output):
        mock_load.return_value = self.loaded_values
        mock_output.side_effect = check_output_side_effects
        config = sysctl.Config("test")

        snapshot = {"vm.swappiness": "1", "other_value": "5"}
        config._restore_snapshot(snapshot)

        mock_output.assert_called_once_with(
            ["sysctl", "vm.swappiness=1", "other_value=5"], stderr=-2, universal_newlines=True
        )

    @patch("charms.operator_libs_linux.v0.sysctl.check_output")
    @patch("charms.operator_libs_linux.v0.sysctl.Config._load_data")
    def test_syctl(self, mock_load, mock_output):
        mock_load.return_value = self.loaded_values
        mock_output.side_effect = check_output_side_effects
        config = sysctl.Config("test")

        result = config._sysctl(["-n", "vm.swappiness"])

        mock_output.assert_called_once_with(
            ["sysctl", "-n", "vm.swappiness"], stderr=-2, universal_newlines=True
        )
        assert result == ["1"]

    @patch("charms.operator_libs_linux.v0.sysctl.check_output")
    @patch("charms.operator_libs_linux.v0.sysctl.Config._load_data")
    def test_syctl_error(self, mock_load, mock_output):
        mock_load.return_value = self.loaded_values
        mock_output.side_effect = check_output_side_effects
        config = sysctl.Config("test")

        with self.assertRaises(sysctl.CommandError) as e:
            config._sysctl(["exception"])

        mock_output.assert_called_once_with(
            ["sysctl", "exception"], stderr=-2, universal_newlines=True
        )
        assert e.exception.message == "Error executing '['sysctl', 'exception']': error on command"

    @patch("charms.operator_libs_linux.v0.sysctl.Config._sysctl")
    @patch("charms.operator_libs_linux.v0.sysctl.Config._load_data")
    def test_apply_without_failed_values(self, mock_load, mock_sysctl):
        mock_load.return_value = self.loaded_values
        mock_sysctl.return_value = ["vm.swappiness = 0"]
        config = sysctl.Config("test")

        config._desired_config = {"vm.swappiness": "0"}
        config._apply()

        mock_sysctl.assert_called_with(["vm.swappiness=0"])

    @patch("charms.operator_libs_linux.v0.sysctl.Config._sysctl")
    @patch("charms.operator_libs_linux.v0.sysctl.Config._load_data")
    def test_apply_with_failed_values(self, mock_load, mock_sysctl):
        mock_load.return_value = self.loaded_values
        mock_sysctl.return_value = [permission_failure_output]
        config = sysctl.Config("test")

        config._desired_config = {"vm.swappiness": "0"}
        with self.assertRaises(sysctl.ApplyError) as e:
            config._apply()

        mock_sysctl.assert_called_with(["vm.swappiness=0"])
        self.assertEqual(e.exception.message, "Unable to set params: ['vm.swappiness']")

    @patch("charms.operator_libs_linux.v0.sysctl.Config._sysctl")
    @patch("charms.operator_libs_linux.v0.sysctl.Config._load_data")
    def test_apply_with_partial_failed_values(self, mock_load, mock_sysctl):
        mock_load.return_value = self.loaded_values
        mock_sysctl.return_value = [permission_failure_output]
        config = sysctl.Config("test")

        config._desired_config = {"vm.swappiness": "0", "net.ipv4.tcp_max_syn_backlog": "4096"}
        with self.assertRaises(sysctl.ApplyError) as e:
            config._apply()

        mock_sysctl.assert_called_with(["vm.swappiness=0", "net.ipv4.tcp_max_syn_backlog=4096"])
        self.assertEqual(e.exception.message, "Unable to set params: ['vm.swappiness']")

    @patch("charms.operator_libs_linux.v0.sysctl.Config._load_data")
    def test_parse_config(self, _):
        config = sysctl.Config("test")

        config._parse_config({"key1": "10", "key2": "20"})

        self.assertEqual(config._desired_config, {"key1": "10", "key2": "20"})

    @patch("charms.operator_libs_linux.v0.sysctl.Config._load_data")
    def test_class_methods(self, mock_load):
        mock_load.return_value = self.loaded_values
        config = sysctl.Config("test")

        # __contains__
        self.assertIn("vm.swappiness", config)
        # __len__
        self.assertEqual(len(config), 2)
        # __iter__
        self.assertListEqual(list(config), list(self.loaded_values.keys()))
        # __getitem__
        for key, value in self.loaded_values.items():
            self.assertEqual(config[key], value)
