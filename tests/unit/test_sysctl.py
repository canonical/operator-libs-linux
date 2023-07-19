# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

import unittest
from pathlib import Path
from subprocess import CalledProcessError
from unittest.mock import call, mock_open, patch

from charms.operator_libs_linux.v0 import sysctl

permission_failure_output = """sysctl: permission denied on key "vm.swappiness", ignoring"""
partial_permission_failure_output = """sysctl: permission denied on key "vm.swappiness", ignoring
net.ipv4.tcp_max_syn_backlog = 4096
"""

TEST_OTHER_CHARM_FILE = """vm.swappiness=60
net.ipv4.tcp_max_syn_backlog=4096
"""
TEST_MERGED_FILE = """# This config file was produced by sysctl lib v0.1
#
# This file represents the output of the sysctl lib, which can combine multiple
# configurations into a single file like.
vm.max_map_count = 262144
vm.swappiness=0

"""
TEST_MULTIPLE_MERGED_FILE = [
    "# This config file was produced by sysctl lib v0.2\n#\n# This file represents the output of the sysctl lib, which can combine multiple\n# configurations into a single file like.\n",
    "vm.swappiness=60\n",
    "net.ipv4.tcp_max_syn_backlog=4096\n",
]
TEST_UPDATE_MERGED_FILE = [
    "# This config file was produced by sysctl lib v0.2\n#\n# This file represents the output of the sysctl lib, which can combine multiple\n# configurations into a single file like.\n",
    "vm.max_map_count=25500\n",
]


def check_output_side_effects(*args, **kwargs):
    if args[0] == ["sysctl", "vm.swappiness", "-n"]:
        return "1"
    elif args[0] == ["sysctl", "other_value", "-n"]:
        return "5"
    elif args[0] == ["sysctl", "vm.swappiness=1", "other_value=5"]:
        return "1\n5"
    elif args[0] == ["sysctl", "vm.swappiness=0"]:
        return permission_failure_output
    elif args[0] == ["sysctl", "vm.swappiness=0", "net.ipv4.tcp_max_syn_backlog=4096"]:
        return partial_permission_failure_output
    elif args[0] == ["sysctl", "exception"]:
        raise CalledProcessError(returncode=1, cmd=args[0], output="error on command")

    # Tests on 'update()'
    elif args[0] == ["sysctl", "vm.max_map_count", "-n"]:
        return "25000"
    elif args[0] == ["sysctl", "vm.max_map_count=25500"]:
        return "25500"


class TestSysctlConfig(unittest.TestCase):
    def setUp(self) -> None:
        self.desired_values = {"vm.swappiness": {"value": 0}}
        self.loaded_values = {"vm.swappiness": "60", "vm.max_map_count": "25500"}

    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.glob")
    @patch("builtins.open", new_callable=mock_open, read_data="vm.max_map_count=25500\n")
    @patch("charms.operator_libs_linux.v0.sysctl.check_output")
    @patch("charms.operator_libs_linux.v0.sysctl.Config._create_charm_file")
    @patch("charms.operator_libs_linux.v0.sysctl.Config._load_data")
    def test_update_new_values(self, mock_load, _, mock_output, mock_file, mock_glob, mock_exists):
        mock_load.return_value = {}
        mock_exists.return_value = False
        mock_glob.return_value = ["/etc/sysctl.d/90-juju-test"]
        mock_output.side_effect = check_output_side_effects
        config = sysctl.Config("test")

        config.update({"vm.max_map_count": {"value": 25500}})

        self.assertEqual(config._desired_config, {"vm.max_map_count": "25500"})
        mock_file.assert_called_with(Path("/etc/sysctl.d/95-juju-sysctl.conf"), "w")
        mock_file.return_value.writelines.assert_called_once_with(TEST_UPDATE_MERGED_FILE)

    @patch("pathlib.Path.exists")
    @patch("charms.operator_libs_linux.v0.sysctl.Config._load_data")
    def test_update_with_validation_error(self, mock_load, mock_exists):
        mock_load.return_value = self.loaded_values
        mock_exists.return_value = False
        config = sysctl.Config("test")

        with self.assertRaises(sysctl.ValidationError) as e:
            config.update({"vm.max_map_count": {"value": 25000}})

        self.assertEqual(e.exception.message, "Validation error for keys: ['vm.max_map_count']")

    @patch("pathlib.Path.exists")
    @patch("charms.operator_libs_linux.v0.sysctl.Config._load_data")
    def test_update_with_permission_error(self, mock_load, mock_exists):
        mock_load.return_value = {}
        mock_exists.return_value = False
        config = sysctl.Config("test")

        with self.assertRaises(sysctl.SysctlPermissionError) as e:
            config.update(
                {"vm.swappiness": {"value": 0}, "net.ipv4.tcp_max_syn_backlog": {"value": 4096}}
            )

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

    @patch("pathlib.Path.exists")
    @patch("builtins.open", new_callable=mock_open, read_data=TEST_MERGED_FILE)
    def test_load_data(self, mock_file, mock_exist):
        config = sysctl.Config(name="test")

        mock_exist.assert_called()
        mock_file.assert_called_with(Path("/etc/sysctl.d/95-juju-sysctl.conf"), "r")
        assert config._data == {"vm.swappiness": "0", "vm.max_map_count": "262144"}

    @patch("pathlib.Path.exists")
    def test_load_data_no_path(self, mock_exist):
        mock_exist.return_value = False
        config = sysctl.Config(name="test")

        mock_exist.assert_called()
        assert len(config) == 0

    @patch("builtins.open", new_callable=mock_open, read_data=TEST_OTHER_CHARM_FILE)
    @patch("pathlib.Path.glob")
    @patch("charms.operator_libs_linux.v0.sysctl.Config._load_data")
    def test_merge(self, mock_load, mock_glob, mock_file):
        mock_glob.return_value = ["/etc/sysctl.d/90-juju-othercharm"]
        mock_load.return_value = self.loaded_values
        config = sysctl.Config("test")

        config._merge()
        mock_glob.assert_called_with("90-juju-*")

        expected_calls = [
            call("/etc/sysctl.d/90-juju-othercharm", "r"),
            call(Path("/etc/sysctl.d/95-juju-sysctl.conf"), "w"),
        ]
        mock_file.assert_has_calls(expected_calls, any_order=True)
        mock_file.return_value.writelines.assert_called_once_with(TEST_MULTIPLE_MERGED_FILE)

    @patch("builtins.open", new_callable=mock_open, read_data=TEST_OTHER_CHARM_FILE)
    @patch("pathlib.Path.glob")
    @patch("charms.operator_libs_linux.v0.sysctl.Config._load_data")
    def test_merge_without_own_file(self, mock_load, mock_glob, mock_file):
        mock_glob.return_value = ["/etc/sysctl.d/90-juju-othercharm", "/etc/sysctl.d/90-juju-test"]
        mock_load.return_value = self.loaded_values
        config = sysctl.Config("test")

        config._merge(add_own_charm=False)
        mock_glob.assert_called_with("90-juju-*")

        expected_calls = [
            call("/etc/sysctl.d/90-juju-othercharm", "r"),
            call(Path("/etc/sysctl.d/95-juju-sysctl.conf"), "w"),
        ]

        assert call("/etc/sysctl.d/90-juju-test", "r") not in mock_file.mock_calls
        mock_file.assert_has_calls(expected_calls, any_order=True)
        mock_file.return_value.writelines.assert_called_once_with(TEST_MULTIPLE_MERGED_FILE)

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

    @patch("builtins.open", new_callable=mock_open)
    @patch("charms.operator_libs_linux.v0.sysctl.Config._load_data")
    def test_create_charm_file(self, mock_load, mock_file):
        mock_load.return_value = self.loaded_values
        config = sysctl.Config("test")

        config._desired_config = {"vm.swappiness": "0", "other_value": "10"}
        config._create_charm_file()

        mock_file.assert_called_with(Path("/etc/sysctl.d/90-juju-test"), "w")
        mock_file.return_value.writelines.assert_called_once_with(
            ["vm.swappiness=0\n", "other_value=10\n"]
        )

    @patch("charms.operator_libs_linux.v0.sysctl.check_output")
    @patch("charms.operator_libs_linux.v0.sysctl.Config._load_data")
    def test_create_snapshot(self, mock_load, mock_output):
        mock_load.return_value = self.loaded_values
        mock_output.side_effect = check_output_side_effects
        config = sysctl.Config("test")

        config._desired_config = {"vm.swappiness": "0", "other_value": "10"}
        snapshot = config._create_snapshot()

        assert mock_output.called_with(["sysctl", "vm.swappiness", "-n"])
        assert mock_output.called_with(["sysctl", "other_value", "-n"])
        assert snapshot == {"vm.swappiness": "1", "other_value": "5"}

    @patch("charms.operator_libs_linux.v0.sysctl.check_output")
    @patch("charms.operator_libs_linux.v0.sysctl.Config._load_data")
    def test_restore_snapshot(self, mock_load, mock_output):
        mock_load.return_value = self.loaded_values
        mock_output.side_effect = check_output_side_effects
        config = sysctl.Config("test")

        snapshot = {"vm.swappiness": "1", "other_value": "5"}
        config._restore_snapshot(snapshot)

        assert mock_output.called_with(["sysctl", "vm.swappiness=1", "other_value=5"])

    @patch("charms.operator_libs_linux.v0.sysctl.check_output")
    @patch("charms.operator_libs_linux.v0.sysctl.Config._load_data")
    def test_syctl(self, mock_load, mock_output):
        mock_load.return_value = self.loaded_values
        mock_output.side_effect = check_output_side_effects
        config = sysctl.Config("test")

        result = config._sysctl(["vm.swappiness", "-n"])

        assert mock_output.called_with(["sysctl", "vm.swappiness", "-n"])
        assert result == ["1"]

    @patch("charms.operator_libs_linux.v0.sysctl.check_output")
    @patch("charms.operator_libs_linux.v0.sysctl.Config._load_data")
    def test_syctl_error(self, mock_load, mock_output):
        mock_load.return_value = self.loaded_values
        mock_output.side_effect = check_output_side_effects
        config = sysctl.Config("test")

        with self.assertRaises(sysctl.SysctlError) as e:
            config._sysctl(["exception"])

        assert mock_output.called_with(["sysctl", "exception"])
        assert e.exception.message == "Error executing '['sysctl', 'exception']': error on command"

    @patch("charms.operator_libs_linux.v0.sysctl.Config._sysctl")
    @patch("charms.operator_libs_linux.v0.sysctl.Config._load_data")
    def test_apply_without_failed_values(self, mock_load, mock_sysctl):
        mock_load.return_value = self.loaded_values
        mock_sysctl.return_value = ["vm.swappiness = 0"]
        config = sysctl.Config("test")

        config._desired_config = {"vm.swappiness": "0"}
        config._apply()

        assert mock_sysctl.called_with(["vm.swappiness=0"])

    @patch("charms.operator_libs_linux.v0.sysctl.Config._sysctl")
    @patch("charms.operator_libs_linux.v0.sysctl.Config._load_data")
    def test_apply_with_failed_values(self, mock_load, mock_sysctl):
        mock_load.return_value = self.loaded_values
        mock_sysctl.return_value = [permission_failure_output]
        config = sysctl.Config("test")

        config._desired_config = {"vm.swappiness": "0"}
        with self.assertRaises(sysctl.SysctlPermissionError) as e:
            config._apply()

        assert mock_sysctl.called_with(["vm.swappiness=0"])
        self.assertEqual(e.exception.message, "Unable to set params: ['vm.swappiness']")

    @patch("charms.operator_libs_linux.v0.sysctl.Config._sysctl")
    @patch("charms.operator_libs_linux.v0.sysctl.Config._load_data")
    def test_apply_with_partial_failed_values(self, mock_load, mock_sysctl):
        mock_load.return_value = self.loaded_values
        mock_sysctl.return_value = [permission_failure_output]
        config = sysctl.Config("test")

        config._desired_config = {"vm.swappiness": "0", "net.ipv4.tcp_max_syn_backlog": "4096"}
        with self.assertRaises(sysctl.SysctlPermissionError) as e:
            config._apply()

        assert mock_sysctl.called_with(["vm.swappiness=0", "net.ipv4.tcp_max_syn_backlog=4096"])
        self.assertEqual(e.exception.message, "Unable to set params: ['vm.swappiness']")

    @patch("charms.operator_libs_linux.v0.sysctl.Config._load_data")
    def test_parse_config(self, _):
        config = sysctl.Config("test")

        config._parse_config({"key1": {"value": 10}, "key2": {"value": "20"}})

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
