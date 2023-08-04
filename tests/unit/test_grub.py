# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.
import io
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import charms.operator_libs_linux.v0.grub as grub
import pytest

GRUB_CONFIG_EXAMPLE_BODY = """
GRUB_RECORDFAIL_TIMEOUT=0
GRUB_TIMEOUT=0
GRUB_TERMINAL=console
GRUB_CMDLINE_LINUX_DEFAULT="$GRUB_CMDLINE_LINUX_DEFAULT hugepagesz=1G"
"""
GRUB_CONFIG_EXAMPLE = f"""
{grub.CONFIG_HEADER}
{grub.CONFIG_DESCRIPTION.format(configs="#  /tmp/test-path")}
# test commented line
{GRUB_CONFIG_EXAMPLE_BODY}
"""
EXP_GRUB_CONFIG = {
    "GRUB_CMDLINE_LINUX_DEFAULT": "$GRUB_CMDLINE_LINUX_DEFAULT hugepagesz=1G",
    "GRUB_RECORDFAIL_TIMEOUT": "0",
    "GRUB_TERMINAL": "console",
    "GRUB_TIMEOUT": "0",
}


def test_validation_error():
    """Test validation error and it's properties."""
    exp_key, exp_message = "test", "test message"

    error = grub.ValidationError(exp_key, exp_message)
    with pytest.raises(ValueError):
        raise error

    assert error.key == exp_key
    assert error.message == exp_message
    assert str(error) == exp_message


@pytest.mark.parametrize(
    "output, exp_result",
    [
        (mock.MagicMock(return_value=b"lxd"), True),
        (mock.MagicMock(side_effect=subprocess.CalledProcessError(1, [])), False),
    ],
)
def test_is_container(output, exp_result):
    """Test helper function to validate if machine is container."""
    with mock.patch("subprocess.check_output", new=output) as mock_check_output:
        assert grub.is_container() == exp_result
        mock_check_output.assert_called_once_with(
            ["/usr/bin/systemd-detect-virt", "--container"], stderr=subprocess.STDOUT
        )


class BaseTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_dir = Path(tmp_dir.name)
        self.addCleanup(tmp_dir.cleanup)

        # configured paths
        grub.GRUB_DIRECTORY = self.tmp_dir
        grub.GRUB_CONFIG = self.tmp_dir / "95-juju-charm.cfg"
        with open(grub.GRUB_CONFIG, "w") as file:
            file.write(GRUB_CONFIG_EXAMPLE)

        # is_container
        mocker_is_container = mock.patch.object(grub, "is_container")
        self.is_container = mocker_is_container.start()
        self.is_container.return_value = False
        self.addCleanup(mocker_is_container.stop)

        # subprocess
        mocker_check_call = mock.patch.object(grub.subprocess, "check_call")
        self.check_call = mocker_check_call.start()
        self.addCleanup(mocker_check_call.stop)


class TestUtils(BaseTest):
    def setUp(self) -> None:
        super().setUp()

        # change logger
        mocked_logger = mock.patch.object(grub, "logger")
        self.logger = mocked_logger.start()
        self.addCleanup(mocked_logger.stop)

    def test_split_config_line(self):
        """Test splitting single line."""
        key, value = grub._split_config_line('test="1234"')
        assert key == "test"
        assert value == "1234"

    def test_split_config_line_failed(self):
        """Test splitting single line."""
        with self.assertRaises(ValueError):
            grub._split_config_line('test="1234" "5678"')

    def test_parse_config(self):
        """Test parsing example GRUB config with skipping duplicated key."""
        stream = io.StringIO(GRUB_CONFIG_EXAMPLE)
        result = grub._parse_config(stream)

        self.assertEqual(result, EXP_GRUB_CONFIG)

    def test_parse_config_with_duplicity(self):
        """Test parsing example GRUB config with skipping duplicated key."""
        raw_config = (
            GRUB_CONFIG_EXAMPLE + 'GRUB_CMDLINE_LINUX_DEFAULT="$GRUB_CMDLINE_LINUX_DEFAULT pti=on"'
        )
        stream = io.StringIO(raw_config)
        result = grub._parse_config(stream)

        self.logger.warning.assert_called_once_with(
            "key %s is duplicated in config", "GRUB_CMDLINE_LINUX_DEFAULT"
        )
        self.assertEqual(
            result["GRUB_CMDLINE_LINUX_DEFAULT"],
            "$GRUB_CMDLINE_LINUX_DEFAULT pti=on",
        )

    def test_load_config_not_exists(self):
        """Test load config from file which does not exist."""
        path = self.tmp_dir / "test_load_config"

        with pytest.raises(FileNotFoundError):
            grub._load_config(path)

    @mock.patch.object(grub, "_parse_config")
    def test_load_config(self, mock_parse_config):
        """Test load config from file."""
        exp_config = {"test": "valid"}
        mock_parse_config.return_value = exp_config
        path = self.tmp_dir / "test_load_config"
        path.touch()  # create file

        with mock.patch.object(grub, "open", mock.mock_open()) as mock_open:
            grub._load_config(path)

        mock_open.assert_called_once_with(path, "r", encoding="UTF-8")
        mock_parse_config.assert_called_once_with(mock_open.return_value)

    def test_save_config(self):
        """Test to save GRUB config file."""
        path = self.tmp_dir / "test-config"

        with mock.patch.object(grub, "open", mock.mock_open()) as mock_open:
            grub._save_config(path, {"test": '"1234"'})

        mock_open.assert_called_once_with(path, "w", encoding="UTF-8")
        mock_open.return_value.write.assert_has_calls(
            [
                mock.call(f"{grub.CONFIG_HEADER}{os.linesep}"),
                mock.call(f"test='\"1234\"'{os.linesep}"),
            ]
        )

    def test_save_config_overwrite(self):
        """Test overwriting if GRUB config already exist."""
        path = self.tmp_dir / "test-config"
        path.touch()

        with mock.patch.object(grub, "open", mock.mock_open()):
            grub._save_config(path, {"test": '"1234"'})

        self.logger.debug.assert_called_once_with(
            "GRUB config %s already exist and it will overwritten", path
        )

    @mock.patch.object(grub, "_load_config")
    @mock.patch.object(grub, "_save_config")
    def test_update_config(self, mock_save, mock_load):
        """Test update existing config file."""
        mock_load.return_value = {"test1": "1", "test2": "2"}
        path = self.tmp_dir / "test-config"
        path.touch()

        grub._update_config(path, {"test2": "22", "test3": "3"})

        mock_load.assert_called_once_with(path)
        mock_save.assert_called_once_with(
            path, {"test1": "1", "test2": "22", "test3": "3"}, grub.CONFIG_HEADER
        )

    @mock.patch.object(grub, "_load_config")
    @mock.patch.object(grub, "_save_config")
    def test_update_not_existing_config(self, mock_save, mock_load):
        """Test update not existing config file."""
        path = self.tmp_dir / "test-config"

        grub._update_config(path, {"test2": "22", "test3": "3"})

        mock_load.assert_not_called()
        mock_save.assert_called_once_with(path, {"test2": "22", "test3": "3"}, grub.CONFIG_HEADER)

    @mock.patch("filecmp.cmp")
    def test_check_update_grub(self, mock_filecmp):
        """Test check update function."""
        grub.check_update_grub()
        self.check_call.assert_called_once_with(
            ["/usr/sbin/grub-mkconfig", "-o", "/tmp/tmp_grub.cfg"], stderr=subprocess.STDOUT
        )
        mock_filecmp.assert_called_once_with(
            Path("/boot/grub/grub.cfg"), Path("/tmp/tmp_grub.cfg")
        )

    @mock.patch("filecmp.cmp")
    def test_check_update_grub_failure(self, mock_filecmp):
        """Test check update function."""
        self.check_call.side_effect = subprocess.CalledProcessError(1, [])

        with self.assertRaises(grub.ApplyError):
            grub.check_update_grub()

        mock_filecmp.assert_not_called()


class TestSmokeConfig(BaseTest):
    def setUp(self) -> None:
        super().setUp()
        # load config
        mocker_load_config = mock.patch.object(grub, "_load_config")
        self.load_config = mocker_load_config.start()
        self.addCleanup(mocker_load_config.stop)
        # save config
        mocker_save_config = mock.patch.object(grub, "_save_config")
        self.save_config = mocker_save_config.start()
        self.addCleanup(mocker_save_config.stop)
        # check_update_grub
        mocker_check_update_grub = mock.patch.object(grub, "check_update_grub")
        self.check_update_grub = mocker_check_update_grub.start()
        self.check_update_grub.return_value = True
        self.addCleanup(mocker_check_update_grub.stop)

        self.name = "charm-a"
        self.config = grub.Config(self.name)
        self.load_config.return_value = EXP_GRUB_CONFIG.copy()

    def test_lazy_data_not_loaded(self):
        """Test data not loaded."""
        self.load_config.assert_not_called()

    def test__contains__(self):
        """Test config __contains__ function."""
        self.assertIn("GRUB_TIMEOUT", self.config)

    def test__len__(self):
        """Test config __len__ function."""
        self.assertEqual(len(self.config), 4)

    def test__iter__(self):
        """Test config __iter__ function."""
        self.assertListEqual(list(self.config), list(EXP_GRUB_CONFIG.keys()))

    def test__getitem__(self):
        """Test config __getitem__ function."""
        for key, value in EXP_GRUB_CONFIG.items():
            self.assertEqual(self.config[key], value)

    def test_data(self):
        """Test data not loaded."""
        self.load_config.return_value = EXP_GRUB_CONFIG
        self.config._lazy_data = None
        assert "test" not in self.config  # this will call config._data once

        self.load_config.assert_called_once_with(grub.GRUB_CONFIG)
        self.assertDictEqual(self.config._data, EXP_GRUB_CONFIG)

    def test_data_no_file(self):
        """Test data not loaded."""
        self.config._lazy_data = None
        self.load_config.side_effect = FileNotFoundError()
        assert "test" not in self.config  # this will call config._data once

        self.load_config.assert_called_once_with(grub.GRUB_CONFIG)
        self.assertDictEqual(self.config._data, {})

    def test_save_grub_config(self):
        """Test save GRUB config."""
        exp_configs = [self.tmp_dir / "90-juju-charm-b", self.tmp_dir / "90-juju-charm-c"]
        [path.touch() for path in exp_configs]  # create files
        exp_data = {"GRUB_TIMEOUT": "1"}

        self.config._lazy_data = exp_data
        self.config._save_grub_configuration()

        self.save_config.assert_called_once_with(grub.GRUB_CONFIG, exp_data, mock.ANY)
        _, _, header = self.save_config.call_args[0]
        self.assertIn(str(self.config.path), header)
        for exp_config_path in exp_configs:
            self.assertIn(str(exp_config_path), header)

    def test_set_new_value(self):
        """Test set new value in config."""
        changed = self.config._set_value("GRUB_NEW_KEY", "1", set())
        self.assertTrue(changed)

    def test_set_existing_value_without_change(self):
        """Test set existing key, but with same value."""
        changed = self.config._set_value("GRUB_TIMEOUT", "0", set())
        self.assertFalse(changed)

    def test_set_existing_value_with_change(self):
        """Test set existing key with new value."""
        changed = self.config._set_value("GRUB_TIMEOUT", "1", set())
        self.assertTrue(changed)

    def test_set_blocked_key(self):
        """Test set new value in config."""
        with pytest.raises(grub.ValidationError):
            self.config._set_value("GRUB_TIMEOUT", "1", {"GRUB_TIMEOUT"})

    def test_update_data(self):
        """Test update GrubConfig _data."""
        data = {"GRUB_TIMEOUT": "1", "GRUB_RECORDFAIL_TIMEOUT": "0"}
        new_data = {"GRUB_NEW_KEY": "test", "GRUB_RECORDFAIL_TIMEOUT": "0"}

        self.config._lazy_data = data
        changed_keys = self.config._update(new_data)
        self.assertEqual({"GRUB_NEW_KEY"}, changed_keys)

    def test_applied_configs(self):
        """Test applied_configs property."""
        exp_configs = {
            self.config.path: self.load_config.return_value,
            self.tmp_dir / "90-juju-charm-b": self.load_config.return_value,
            self.tmp_dir / "90-juju-charm-c": self.load_config.return_value,
        }
        [path.touch() for path in exp_configs]  # create files

        self.assertEqual(self.config.applied_configs, exp_configs)

    def test_blocked_keys(self):
        """Test blocked_keys property."""
        exp_configs = {
            self.config.path: {"A": "1", "B": "2"},
            self.tmp_dir / "90-juju-charm-b": {"B": "3", "C": "2"},
            self.tmp_dir / "90-juju-charm-c": {"D": "4"},
        }

        with mock.patch.object(
            grub.Config, "applied_configs", new=mock.PropertyMock(return_value=exp_configs)
        ):
            blocked_keys = self.config.blocked_keys

        self.assertSetEqual(blocked_keys, {"B", "C", "D"})

    def test_path(self):
        """Test path property."""
        self.assertEqual(self.config.path, self.tmp_dir / f"90-juju-{self.name}")

    def test_apply_without_changes(self):
        """Test applying GRUB config without any changes."""
        self.check_update_grub.return_value = False
        self.config.apply()

        self.check_update_grub.assert_called_once_with()
        self.check_call.assert_not_called()

    def test_apply_failure(self):
        """Test applying GRUB config failure."""
        self.check_call.side_effect = subprocess.CalledProcessError(1, [])
        with self.assertRaises(grub.ApplyError):
            self.config.apply()

    def test_apply(self):
        """Test applying GRUB config failure."""
        self.config.apply()
        self.check_update_grub.assert_called_once_with()
        self.check_call.assert_called_once_with(
            ["/usr/sbin/update-grub"], stderr=subprocess.STDOUT
        )

    @mock.patch.object(grub.Config, "apply")
    @mock.patch.object(grub.Config, "_save_grub_configuration")
    def test_remove_no_config(self, mock_save, mock_apply):
        """Test removing when there is no charm config."""
        self.config.path.unlink(missing_ok=True)  # remove charm config file
        changed_keys = self.config.remove()

        self.assertSetEqual(changed_keys, set())
        mock_save.assert_not_called()
        mock_apply.assert_not_called()

    @mock.patch.object(grub.Config, "apply")
    @mock.patch.object(grub.Config, "_save_grub_configuration")
    def test_remove_no_apply(self, mock_save, mock_apply):
        """Test removing without applying."""
        self.config.path.touch()  # created charm file
        changed_keys = self.config.remove(apply=False)

        self.assertFalse(self.config.path.exists())
        self.assertSetEqual(changed_keys, set(EXP_GRUB_CONFIG.keys()))
        mock_save.assert_called_once_with()
        mock_apply.assert_not_called()

    @mock.patch.object(grub.Config, "apply")
    @mock.patch.object(grub.Config, "applied_configs", call=mock.PropertyMock)
    @mock.patch.object(grub.Config, "_save_grub_configuration")
    def test_remove(self, mock_save, mock_applied_configs, mock_apply):
        """Test removing with applying."""
        self.config.path.touch()  # created charm file
        mock_applied_configs.values.return_value = [
            {key: value for key, value in EXP_GRUB_CONFIG.items() if key != "GRUB_TIMEOUT"}
        ]

        changed_keys = self.config.remove()

        self.assertFalse(self.config.path.exists())
        self.assertSetEqual(changed_keys, {"GRUB_TIMEOUT"})
        mock_save.assert_called_once_with()
        mock_apply.assert_called_once_with()

    @mock.patch.object(grub.Config, "apply")
    @mock.patch.object(grub.Config, "_save_grub_configuration")
    @mock.patch.object(grub, "_update_config")
    def test_update_on_container(self, mock_update, mock_save, mock_apply):
        """Test update current GRUB config on container."""
        self.is_container.return_value = True

        with self.assertRaises(grub.IsContainerError):
            self.config.update({"GRUB_TIMEOUT": "0"})

        self.assertDictEqual(self.config._data, EXP_GRUB_CONFIG, "config was changed")
        mock_save.assert_not_called()
        mock_apply.assert_not_called()
        mock_update.assert_not_called()

    @mock.patch.object(grub.Config, "apply")
    @mock.patch.object(grub.Config, "_save_grub_configuration")
    @mock.patch.object(grub.Config, "_update")
    @mock.patch.object(grub, "_update_config")
    def test_update_validation_failure(
        self, mock_update_config, mock_update, mock_save, mock_apply
    ):
        """Test update current GRUB config with validation failure."""
        mock_update.side_effect = grub.ValidationError("GRUB_TIMEOUT", "failed")

        with self.assertRaises(grub.ValidationError):
            # trying to set already existing key with different value -> ValidationError
            self.config.update({"GRUB_TIMEOUT": "1"})

        self.assertDictEqual(self.config._data, EXP_GRUB_CONFIG, "snapshot was not restored")
        mock_save.assert_not_called()
        mock_apply.assert_not_called()
        mock_update_config.assert_not_called()

    @mock.patch.object(grub.Config, "apply")
    @mock.patch.object(grub.Config, "_save_grub_configuration")
    @mock.patch.object(grub, "_update_config")
    def test_update_apply_failure(self, mock_update, mock_save, mock_apply):
        """Test update current GRUB config with applied failure."""
        mock_apply.side_effect = grub.ApplyError()

        with self.assertRaises(grub.ApplyError):
            self.config.update({"GRUB_NEW_KEY": "1"})

        self.assertDictEqual(self.config._data, EXP_GRUB_CONFIG, "snapshot was not restored")
        mock_save.assert_has_calls([mock.call(), mock.call()])
        mock_apply.assert_called_once_with()
        mock_update.assert_not_called()

    @mock.patch.object(grub.Config, "apply")
    @mock.patch.object(grub.Config, "_save_grub_configuration")
    @mock.patch.object(grub, "_update_config")
    def test_update_without_changes(self, mock_update, mock_save, mock_apply):
        """Test update current GRUB config without any changes."""
        # running with same key and value from example above
        config = {"GRUB_TIMEOUT": "0"}
        changed_keys = self.config.update(config)

        self.assertSetEqual(changed_keys, set())
        mock_save.assert_not_called()
        mock_apply.assert_not_called()
        mock_update.assert_called_once_with(self.config.path, config)

    @mock.patch.object(grub.Config, "apply")
    @mock.patch.object(grub.Config, "_save_grub_configuration")
    @mock.patch.object(grub, "_update_config")
    def test_update_current_configuration(self, mock_update, mock_save, mock_apply):
        """Test update current GRUB config with different values.

        This test is simulating the scenario, when same charm want to change it's own
        values.
        """
        # running with same key, but different value from example above
        config = {"GRUB_TIMEOUT": "1"}
        changed_keys = self.config.update(config)

        self.assertSetEqual(changed_keys, set(config.keys()))
        mock_save.assert_called_once_with()
        mock_apply.assert_called_once_with()
        mock_update.assert_called_once_with(self.config.path, config)

    @mock.patch.object(grub.Config, "apply")
    @mock.patch.object(grub.Config, "_save_grub_configuration")
    @mock.patch.object(grub, "_update_config")
    def test_update_without_apply(self, mock_update, mock_save, mock_apply):
        """Test update current GRUB config with different values.

        This test is simulating the scenario, when same charm want to change it's own
        values.
        """
        # running with same key, but different value from example above
        config = {"GRUB_TIMEOUT": "1"}
        changed_keys = self.config.update(config, apply=False)

        self.assertSetEqual(changed_keys, set(config.keys()))
        mock_save.assert_called_once_with()
        mock_apply.assert_not_called()
        mock_update.assert_called_once_with(self.config.path, config)


class TestFullConfig(BaseTest):
    """The tests contains minimal mocks to test more details."""

    def setUp(self) -> None:
        super().setUp()

        # filecmp
        mocker_filecmp = mock.patch.object(grub, "filecmp")
        self.filecmp = mocker_filecmp.start()
        self.filecmp.cmp.return_value = False  # check_update_grub -> True
        self.addCleanup(mocker_filecmp.stop)

        # define and create test charm configs
        self.configs = {
            "charm-1": {
                "GRUB_TIMEOUT": EXP_GRUB_CONFIG["GRUB_TIMEOUT"],
                "GRUB_RECORDFAIL_TIMEOUT": EXP_GRUB_CONFIG["GRUB_RECORDFAIL_TIMEOUT"],
                "GRUB_CMDLINE_LINUX_DEFAULT": EXP_GRUB_CONFIG["GRUB_CMDLINE_LINUX_DEFAULT"],
            },
            "charm-2": {"GRUB_TIMEOUT": EXP_GRUB_CONFIG["GRUB_TIMEOUT"]},
            "charm-3": {
                "GRUB_TERMINAL": EXP_GRUB_CONFIG["GRUB_TERMINAL"],
                "GRUB_CMDLINE_LINUX_DEFAULT": EXP_GRUB_CONFIG["GRUB_CMDLINE_LINUX_DEFAULT"],
            },
        }
        for name, conf in self.configs.items():
            grub._save_config(self.tmp_dir / f"{grub.CHARM_CONFIG_PREFIX}-{name}", conf)

    def test_remove(self):
        """Test removing config for current charm."""
        name = "charm-1"
        exp_changed_keys = {"GRUB_RECORDFAIL_TIMEOUT"}
        config = grub.Config(name)
        self.assertTrue(config.path.exists(), "missing required file for test")

        changed_keys = config.remove()

        self.assertFalse(config.path.exists())
        self.assertSetEqual(changed_keys, exp_changed_keys)
        self.assertDictEqual(
            config._data,
            {
                "GRUB_TIMEOUT": "0",
                "GRUB_TERMINAL": "console",
                "GRUB_CMDLINE_LINUX_DEFAULT": "$GRUB_CMDLINE_LINUX_DEFAULT hugepagesz=1G",
            },
        )
        self.filecmp.cmp.assert_called_once_with(
            Path("/boot/grub/grub.cfg"), Path("/tmp/tmp_grub.cfg")
        )
        self.check_call.assert_has_calls(
            [
                mock.call(
                    ["/usr/sbin/grub-mkconfig", "-o", "/tmp/tmp_grub.cfg"],
                    stderr=subprocess.STDOUT,
                ),
                mock.call(["/usr/sbin/update-grub"], stderr=subprocess.STDOUT),
            ]
        )

    def test_update_validation_error(self):
        """Test update raising ValidationError."""
        name = "charm-1"
        new_config = {"GRUB_TIMEOUT": "1"}
        exp_config = EXP_GRUB_CONFIG
        exp_charm_config = self.configs[name]

        config = grub.Config(name)

        with pytest.raises(grub.ValidationError):
            config.update(new_config)

        self.assertDictEqual(config._data, exp_config)
        self.assertDictEqual(grub._load_config(grub.GRUB_CONFIG), exp_config)
        self.assertDictEqual(grub._load_config(config.path), exp_charm_config)
        self.filecmp.cmp.assert_not_called()
        self.check_call.assert_not_called()

    def test_update(self):
        """Test successful update."""
        name = "charm-1"
        new_config = {"GRUB_RECORDFAIL_TIMEOUT": "1"}
        exp_config = {**EXP_GRUB_CONFIG, **new_config}
        exp_charm_config = {**self.configs[name], **new_config}

        config = grub.Config(name)

        changed_keys = config.update(new_config)

        self.assertSetEqual(changed_keys, set(new_config.keys()))
        self.assertDictEqual(config._data, exp_config)
        self.assertDictEqual(grub._load_config(grub.GRUB_CONFIG), exp_config)
        self.assertDictEqual(grub._load_config(config.path), exp_charm_config)
        self.filecmp.cmp.assert_called_once_with(
            Path("/boot/grub/grub.cfg"), Path("/tmp/tmp_grub.cfg")
        )
        self.check_call.assert_has_calls(
            [
                mock.call(
                    ["/usr/sbin/grub-mkconfig", "-o", "/tmp/tmp_grub.cfg"],
                    stderr=subprocess.STDOUT,
                ),
                mock.call(["/usr/sbin/update-grub"], stderr=subprocess.STDOUT),
            ]
        )
