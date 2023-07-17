# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.
import io
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


class BaseTestGrubLib(unittest.TestCase):
    def setUp(self) -> None:
        tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_dir = Path(tmp_dir.name)
        self.addCleanup(tmp_dir.cleanup)

        # configured paths
        grub.GRUB_DIRECTORY = self.tmp_dir

        # change logger
        mocked_logger = mock.patch.object(grub, "logger")
        self.logger = mocked_logger.start()
        self.addCleanup(mocked_logger.stop)


class TestGrubUtils(BaseTestGrubLib):
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
        mock_open.return_value.writelines.assert_called_once_with([mock.ANY, "test='\"1234\"'"])

    def test_save_config_overwrite(self):
        """Test overwriting if GRUB config already exist."""
        path = self.tmp_dir / "test-config"
        path.touch()

        with mock.patch.object(grub, "open", mock.mock_open()):
            grub._save_config(path, {"test": '"1234"'})

        self.logger.debug.assert_called_once_with(
            "GRUB config %s already exist and it will overwritten", path
        )

    @mock.patch("subprocess.check_call")
    @mock.patch("filecmp.cmp")
    def test_check_update_grub(self, mock_filecmp, mock_check_call):
        """Test check update function."""
        grub.check_update_grub()
        mock_check_call.assert_called_once_with(
            ["/usr/sbin/grub-mkconfig", "-o", "/tmp/tmp_grub.cfg"], stderr=subprocess.STDOUT
        )
        mock_filecmp.assert_called_once_with(
            Path("/boot/grub/grub.cfg"), Path("/tmp/tmp_grub.cfg")
        )

    @mock.patch("subprocess.check_call")
    @mock.patch("filecmp.cmp")
    def test_check_update_grub_failure(self, mock_filecmp, mock_check_call):
        """Test check update function."""
        mock_check_call.side_effect = subprocess.CalledProcessError(1, [])

        with self.assertRaises(subprocess.CalledProcessError):
            grub.check_update_grub()

        mock_filecmp.assert_not_called()


class TestGrubConfig(BaseTestGrubLib):
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
        # is_container
        mocker_is_container = mock.patch.object(grub, "is_container")
        self.is_container = mocker_is_container.start()
        self.is_container.return_value = False
        self.addCleanup(mocker_is_container.stop)
        # check_update_grub
        mocker_check_update_grub = mock.patch.object(grub, "check_update_grub")
        self.check_update_grub = mocker_check_update_grub.start()
        self.addCleanup(mocker_check_update_grub.stop)

        self.name = "charm-a"
        self.path = self.tmp_dir / f"90-juju-{self.name}"
        with open(self.path, "w") as file:
            # create example of charm-a config
            file.write(GRUB_CONFIG_EXAMPLE_BODY)
        self.config = grub.Config(self.name)
        self.config._lazy_data = EXP_GRUB_CONFIG.copy()

    def test_lazy_data_not_loaded(self):
        """Test data not loaded."""
        self.load_config.assert_not_called()

    def test__contains__(self):
        """Tets config __contains__ function."""
        self.assertIn("GRUB_TIMEOUT", self.config)

    def test__len__(self):
        """Tets config __len__ function."""
        self.assertEqual(len(self.config), 4)

    def test__iter__(self):
        """Tets config __iter__ function."""
        self.assertListEqual(list(self.config), list(EXP_GRUB_CONFIG.keys()))

    def test__getitem__(self):
        """Tets config __getitem__ function."""
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
            self.path: self.load_config.return_value,
            self.tmp_dir / "90-juju-charm-b": self.load_config.return_value,
            self.tmp_dir / "90-juju-charm-c": self.load_config.return_value,
        }
        [path.touch() for path in exp_configs]  # create files

        self.assertEqual(self.config.applied_configs, exp_configs)

    def test_blocked_keys(self):
        """Test blocked_keys property."""
        exp_configs = {
            self.path: {"A": "1", "B": "2"},
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

    @mock.patch("subprocess.check_call")
    def test_apply_without_changes(self, mock_call):
        """Test applying GRUB config without any changes."""
        self.check_update_grub.return_value = False
        self.config.apply()

        self.check_update_grub.assert_called_once()
        mock_call.assert_not_called()

    @mock.patch("subprocess.check_call")
    def test_apply_with_new_changes(self, mock_call):
        """Test applying GRUB config."""
        self.check_update_grub.return_value = True
        self.config.apply()

        self.check_update_grub.assert_called_once()
        mock_call.assert_called_once_with(["/usr/sbin/update-grub"], stderr=subprocess.STDOUT)

    @mock.patch("subprocess.check_call")
    def test_apply_failure(self, mock_call):
        """Test applying GRUB config failure."""
        mock_call.side_effect = subprocess.CalledProcessError(1, [])
        with self.assertRaises(grub.ApplyError):
            self.config.apply()

    @mock.patch.object(grub.Config, "apply")
    @mock.patch.object(grub.Config, "_save_grub_configuration")
    def test_remove_no_config(self, mock_save, mock_apply):
        """Test removing when there is no charm config."""
        self.config.path.unlink()  # remove charm config file
        changed_keys = self.config.remove()

        self.assertSetEqual(changed_keys, set())
        mock_save.assert_not_called()
        mock_apply.assert_not_called()

    @mock.patch.object(grub.Config, "apply")
    @mock.patch.object(grub.Config, "_save_grub_configuration")
    def test_remove_no_apply(self, mock_save, mock_apply):
        """Test removing without applying."""
        changed_keys = self.config.remove(apply=False)

        self.assertSetEqual(changed_keys, set(EXP_GRUB_CONFIG.keys()))
        mock_save.assert_called_once()
        mock_apply.assert_not_called()

    @mock.patch.object(grub.Config, "apply")
    @mock.patch.object(grub.Config, "_save_grub_configuration")
    def test_remove(self, mock_save, mock_apply):
        """Test removing config for current charm."""
        exp_changed_keys = {"GRUB_RECORDFAIL_TIMEOUT"}
        exp_configs = {
            self.name: EXP_GRUB_CONFIG,
            "charm-b": {"GRUB_TIMEOUT": "0"},
            "charm-c": {
                "GRUB_TERMINAL": "console",
                "GRUB_CMDLINE_LINUX_DEFAULT": '"$GRUB_CMDLINE_LINUX_DEFAULT hugepagesz=1G"',
            },
        }
        self.load_config.side_effect = [exp_configs["charm-b"], exp_configs["charm-c"]]
        (self.tmp_dir / "90-juju-charm-b").touch()
        (self.tmp_dir / "90-juju-charm-c").touch()

        changed_keys = self.config.remove()

        self.assertFalse((self.tmp_dir / self.name).exists())
        self.load_config.assert_has_calls(
            [
                mock.call(self.tmp_dir / f"90-juju-{charm}")
                for charm in exp_configs
                if charm != self.name
            ]
        )
        self.assertSetEqual(changed_keys, exp_changed_keys)
        self.assertDictEqual(
            self.config._data,
            {
                "GRUB_TIMEOUT": "0",
                "GRUB_TERMINAL": "console",
                "GRUB_CMDLINE_LINUX_DEFAULT": '"$GRUB_CMDLINE_LINUX_DEFAULT hugepagesz=1G"',
            },
        )
        mock_save.assert_called_once()
        mock_apply.assert_called_once()

    @mock.patch.object(grub.Config, "apply")
    @mock.patch.object(grub.Config, "_save_grub_configuration")
    def test_update_on_container(self, mock_save, mock_apply):
        """Test update current GRUB config on container."""
        self.is_container.return_value = True

        with self.assertRaises(grub.IsContainerError):
            self.config.update({"GRUB_TIMEOUT": "0"})

        mock_save.assert_not_called()
        mock_apply.assert_not_called()
        self.assertDictEqual(self.config._data, EXP_GRUB_CONFIG, "config was changed")

    @mock.patch.object(grub.Config, "apply")
    @mock.patch.object(grub.Config, "_save_grub_configuration")
    @mock.patch.object(
        grub.Config, "_set_value", side_effect=grub.ValidationError("test", "test_message")
    )
    def test_update_validation_failure(self, _, mock_save, mock_apply):
        """Test update current GRUB config with validation failure."""
        with self.assertRaises(grub.ValidationError):
            # trying to set already existing key with different value -> ValidationError
            self.config.update({"GRUB_TIMEOUT": "1"})

        mock_save.assert_not_called()
        mock_apply.assert_not_called()
        self.assertDictEqual(self.config._data, EXP_GRUB_CONFIG, "config was changed")

    @mock.patch.object(grub.Config, "apply")
    @mock.patch.object(grub.Config, "_save_grub_configuration")
    def test_update_apply_failure(self, mock_save, mock_apply):
        """Test update current GRUB config with applied failure."""
        mock_apply.side_effect = grub.ApplyError("failed to apply")

        with self.assertRaises(grub.ApplyError):
            self.config.update({"GRUB_NEW_KEY": "1"})

        mock_save.assert_has_calls(
            [mock.call()] * 2,
            "it should be called once before apply and one after snapshot restore",
        )
        mock_apply.assert_called_once()
        self.assertDictEqual(self.config._data, EXP_GRUB_CONFIG, "snapshot was not restored")

    @mock.patch.object(grub.Config, "apply")
    @mock.patch.object(grub.Config, "_save_grub_configuration")
    def test_update_without_changes(self, mock_save, mock_apply):
        """Test update current GRUB config without any changes."""
        changed_keys = self.config.update({"GRUB_TIMEOUT": "0"})

        self.assertSetEqual(changed_keys, set())
        mock_save.assert_not_called()
        mock_apply.assert_not_called()
        self.save_config.assert_called_once_with(self.path, mock.ANY)
        self.assertDictEqual(self.config._data, EXP_GRUB_CONFIG)

    @mock.patch.object(grub.Config, "apply")
    @mock.patch.object(grub.Config, "_save_grub_configuration")
    def test_update(self, mock_save, mock_apply):
        """Test update current GRUB config without applying it."""
        new_config = {"GRUB_NEW_KEY": "1"}
        exp_config = {**EXP_GRUB_CONFIG, **new_config}

        self.config.update(new_config)

        mock_save.assert_called_once()
        mock_apply.assert_called_once()
        self.save_config.assert_called_once_with(self.path, new_config)
        self.assertDictEqual(self.config._data, exp_config)

    @mock.patch.object(grub.Config, "apply")
    @mock.patch.object(grub.Config, "_save_grub_configuration")
    def test_update_same_charm(self, *_):
        """Test update current GRUB config twice with different values.

        This test is simulating the scenario, when same charm want to change it's own
        values.
        """
        first_config = {"GRUB_NEW_KEY": "0"}
        new_config = {"GRUB_NEW_KEY": "1"}
        exp_config = {**EXP_GRUB_CONFIG, **new_config}

        self.config.update(first_config)
        self.config.update(new_config)

        self.assertDictEqual(self.config._data, exp_config)

    @mock.patch.object(grub.Config, "apply")
    @mock.patch.object(grub.Config, "_save_grub_configuration")
    def test_update_without_apply(self, mock_save, mock_apply):
        """Test update current GRUB config without applying it."""
        self.config.update({"GRUB_NEW_KEY": "1"}, apply=False)

        mock_save.assert_called_once()
        mock_apply.assert_not_called()
        self.save_config.assert_called_once_with(self.path, mock.ANY)
