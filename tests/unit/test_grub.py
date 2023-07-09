# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import charms.operator_libs_linux.v0.grub as grub
import pytest

GRUB_CONFIG_EXAMPLE_DESCRIPTION = grub.CONFIG_DESCRIPTION.format(
    configs=grub.FILE_LINE_IN_DESCRIPTION.format(path="/tmp/test-charm")
)
GRUB_CONFIG_EXAMPLE = f"""
{grub.CONFIG_HEADER}
{GRUB_CONFIG_EXAMPLE_DESCRIPTION}

GRUB_RECORDFAIL_TIMEOUT=0
GRUB_TIMEOUT=0
GRUB_TERMINAL=console
GRUB_CMDLINE_LINUX_DEFAULT="$GRUB_CMDLINE_LINUX_DEFAULT hugepagesz=1G"
"""
EXP_GRUB_CONFIG = {
    "GRUB_CMDLINE_LINUX_DEFAULT": '"$GRUB_CMDLINE_LINUX_DEFAULT hugepagesz=1G"',
    "GRUB_RECORDFAIL_TIMEOUT": "0",
    "GRUB_TERMINAL": "console",
    "GRUB_TIMEOUT": "0",
}


def test_validation_error():
    """Test validation error and it's properties."""
    error = grub.ValidationError("test", "test message")
    with pytest.raises(ValueError):
        raise error

    assert error.key == "test"
    assert error.message == "test message"


class BaseTestGrubLib(unittest.TestCase):
    def setUp(self) -> None:
        tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_dir = Path(tmp_dir.name)
        self.addCleanup(tmp_dir.cleanup)

        # configured paths
        grub.LIB_CONFIG_DIRECTORY = self.tmp_dir
        grub.GRUB_CONFIG = self.tmp_dir / "95-juju-charm.cfg"

        # change logger
        mocked_logger = mock.patch.object(grub, "logger")
        self.logger = mocked_logger.start()
        self.addCleanup(mocked_logger.stop)


class TestGrubUtils(BaseTestGrubLib):
    def test_parse_config(self):
        """Test parsing example grub config with skipping duplicated key."""
        result = grub._parse_config(GRUB_CONFIG_EXAMPLE)

        self.assertEqual(result, EXP_GRUB_CONFIG)

    def test_parse_config_with_duplicity(self):
        """Test parsing example grub config with skipping duplicated key."""
        raw_config = (
            GRUB_CONFIG_EXAMPLE + 'GRUB_CMDLINE_LINUX_DEFAULT="$GRUB_CMDLINE_LINUX_DEFAULT pti=on"'
        )

        result = grub._parse_config(raw_config)

        self.logger.warning.assert_called_once_with(
            "key %s is duplicated in config", "GRUB_CMDLINE_LINUX_DEFAULT"
        )
        self.assertEqual(
            result["GRUB_CMDLINE_LINUX_DEFAULT"], '"$GRUB_CMDLINE_LINUX_DEFAULT pti=on"'
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

        with mock.patch.object(grub, "open", mock.mock_open(read_data="test")) as mock_open:
            grub._load_config(path)

        mock_open.assert_called_once_with(path, "r", encoding="UTF-8")
        mock_parse_config.assert_called_once_with("test")

    def test_save_config(self):
        """Test to save grub config file."""
        path = self.tmp_dir / "test-config"

        with mock.patch.object(grub, "open", mock.mock_open()) as mock_open:
            grub._save_config(path, {"test": '"1234"'})

        mock_open.assert_called_once_with(path, "w", encoding="UTF-8")
        mock_open.return_value.writelines.assert_called_once_with([mock.ANY, 'test="1234"'])

    def test_save_config_overwrite(self):
        """Test overwriting if grub config already exist."""
        path = self.tmp_dir / "test-config"
        path.touch()

        with mock.patch.object(grub, "open", mock.mock_open()):
            grub._save_config(path, {"test": '"1234"'})

        self.logger.debug.assert_called_once_with(
            "grub config %s already exist and it will overwritten", path
        )


class TestGrubConfig(BaseTestGrubLib):
    def setUp(self) -> None:
        super().setUp()
        mocker_load_config = mock.patch.object(grub, "_load_config")
        self.mock_load_config = mocker_load_config.start()
        self.mock_load_config.return_value = EXP_GRUB_CONFIG
        self.addCleanup(mocker_load_config.stop)

    def test_lazy_data_not_loaded(self):
        """Test data not loaded."""
        _ = grub.GrubConfig()

        self.mock_load_config.assert_not_called()

    def test__contains__(self):
        """Tets config __contains__ function."""
        config = grub.GrubConfig()
        self.assertIn("GRUB_TIMEOUT", config)

    def test__len__(self):
        """Tets config __len__ function."""
        config = grub.GrubConfig()
        self.assertEqual(len(config), 4)

    def test__iter__(self):
        """Tets config __iter__ function."""
        config = grub.GrubConfig()
        self.assertListEqual(list(config), list(EXP_GRUB_CONFIG.keys()))

    def test__getitem__(self):
        """Tets config __getitem__ function."""
        config = grub.GrubConfig()
        for key, value in EXP_GRUB_CONFIG.items():
            self.assertEqual(config[key], value)

    def test_data(self):
        """Test data not loaded."""
        config = grub.GrubConfig()
        assert "test" not in config  # this will call config._data once

        self.mock_load_config.assert_called_once_with(grub.GRUB_CONFIG)
        self.assertDictEqual(config._data, EXP_GRUB_CONFIG)

    @mock.patch.object(grub, "_save_config")
    def test_save_grub_config(self, mock_save_config):
        """Test save grub config."""
        charm = "charm-c"
        exp_path = self.tmp_dir / charm
        exp_configs = [self.tmp_dir / "charm-a", self.tmp_dir / "charm-b"]
        exp_data = {"GRUB_TIMEOUT": "1"}

        with mock.patch.object(
            grub.GrubConfig, "path", new=mock.PropertyMock(return_value=exp_path)
        ) and mock.patch.object(
            grub.GrubConfig, "applied_configs", new=mock.PropertyMock(return_value=exp_configs)
        ):
            config = grub.GrubConfig(charm)
            config._lazy_data = exp_data
            config._save_grub_configuration()

        mock_save_config.assert_called_once_with(grub.GRUB_CONFIG, exp_data, mock.ANY)
        _, _, header = mock_save_config.call_args[0]
        self.assertIn(str(exp_path), header)
        for exp_config_path in exp_configs:
            self.assertIn(str(exp_config_path), header)

    def test_set_new_value(self):
        """Test set new value in config."""
        config = grub.GrubConfig()
        changed = config._set_value("GRUB_NEW_KEY", "1")

        self.assertTrue(changed)

    def test_set_existing_value_without_change(self):
        """Test set new value in config."""
        config = grub.GrubConfig()
        changed = config._set_value("GRUB_TIMEOUT", "0")

        self.assertFalse(changed)

    def test_set_existing_value_with_change(self):
        """Test set new value in config."""
        config = grub.GrubConfig()
        with pytest.raises(grub.ValidationError):
            config._set_value("GRUB_TIMEOUT", "1")

    def test_update_data(self):
        """Test update GrubConfig _data."""
        data = {"GRUB_TIMEOUT": "1", "GRUB_RECORDFAIL_TIMEOUT": "0"}
        new_data = {"GRUB_NEW_KEY": "test", "GRUB_RECORDFAIL_TIMEOUT": "0"}

        config = grub.GrubConfig("charm-a")
        config._lazy_data = data
        changed_keys = config._update(new_data)
        self.assertEqual({"GRUB_NEW_KEY"}, changed_keys)

    @mock.patch.object(grub, "os")
    def test_charm_name(self, mock_os):
        """Test define charm name or using value from JUJU_UNIT_NAME env."""
        exp_charm_name = "test-charm"
        mock_os.getenv.return_value = exp_charm_name

        # define charm name in init
        config = grub.GrubConfig(exp_charm_name)
        self.assertEqual(config.charm_name, exp_charm_name)
        mock_os.assert_not_called()

        # get charm name from env
        config = grub.GrubConfig()
        self.assertEqual(config.charm_name, exp_charm_name)
        mock_os.getenv.assert_called_once_with("JUJU_UNIT_NAME", "unknown")

    def test_path(self):
        """Test path property."""
        exp_charm = "charm-a"

        config = grub.GrubConfig(exp_charm)
        self.assertEqual(config.path, self.tmp_dir / exp_charm)

    def test_applied_configs(self):
        """Test registered_configs property."""
        exp_configs = [self.tmp_dir / "charm-a", self.tmp_dir / "charm-b"]
        [path.touch() for path in exp_configs]

        config = grub.GrubConfig("charm-d")
        self.assertEqual(config.applied_configs, exp_configs)

    @mock.patch.object(grub, "_load_config")
    @mock.patch.object(grub.GrubConfig, "_apply")
    @mock.patch.object(grub.GrubConfig, "_save_grub_configuration")
    def test_remove(self, mock_save, mock_apply, mock_load_config):
        """Test removing config for current charm."""
        exp_charm = "charm-a"
        exp_configs = {
            "charm-a": {"GRUB_RECORDFAIL_TIMEOUT": "0"},
            "charm-b": {"GRUB_TIMEOUT": "0"},
            "charm-c": {
                "GRUB_TERMINAL": "console",
                "GRUB_CMDLINE_LINUX_DEFAULT": '"$GRUB_CMDLINE_LINUX_DEFAULT hugepagesz=1G"',
            },
        }
        mock_load_config.side_effect = reversed(exp_configs.values())
        [(self.tmp_dir / charm).touch() for charm in exp_configs]  # create files

        config = grub.GrubConfig(exp_charm)
        config.remove()

        self.assertFalse((self.tmp_dir / exp_charm).exists())
        mock_load_config.assert_has_calls(
            [mock.call(self.tmp_dir / charm) for charm in exp_configs if charm != exp_charm]
        )
        self.assertDictEqual(
            config._data,
            {
                "GRUB_TIMEOUT": "0",
                "GRUB_TERMINAL": "console",
                "GRUB_CMDLINE_LINUX_DEFAULT": '"$GRUB_CMDLINE_LINUX_DEFAULT hugepagesz=1G"',
            },
        )
        mock_save.assert_called_once()
        mock_apply.assert_called_once()

    @mock.patch.object(grub, "is_container", return_value=True)
    def test_update_on_container(self, _):
        """Test update current grub config on container."""
        config = grub.GrubConfig("charm-a")
        with self.assertRaises(grub.IsContainerError):
            config.update({"GRUB_TIMEOUT": "1"})

        self.assertDictEqual(config._data, EXP_GRUB_CONFIG)

    @mock.patch.object(grub, "is_container", return_value=False)
    @mock.patch.object(grub.GrubConfig, "_save_grub_configuration")
    def test_update_with_validation_failure(self, mock_save, _):
        """Test update current grub config with validation error."""
        config = grub.GrubConfig("charm-a")
        with self.assertRaises(grub.ValidationError):
            config.update({"GRUB_TIMEOUT": "1"})

        self.assertDictEqual(config._data, EXP_GRUB_CONFIG)
        mock_save.assert_not_called()

    @mock.patch.object(grub, "is_container", return_value=False)
    @mock.patch.object(
        grub.subprocess,
        "check_call",
        side_effect=[subprocess.CalledProcessError(1, ["echo"]), None],
    )
    @mock.patch.object(grub.GrubConfig, "_save_grub_configuration")
    def test_update_with_apply_failure_due_mkconfig(self, mock_save, *_):
        """Test update current grub config with apply error due mkconfig failure."""
        config = grub.GrubConfig("charm-a")
        with self.assertRaises(grub.ApplyError):
            config.update({"GRUB_TIMEOUT": "0"})

        self.assertDictEqual(config._data, EXP_GRUB_CONFIG)
        self.assertEqual(len(mock_save.mock_calls), 2)

    @mock.patch.object(grub, "is_container", return_value=False)
    @mock.patch.object(
        grub.subprocess,
        "check_call",
        side_effect=[None, subprocess.CalledProcessError(1, ["echo"])],
    )
    @mock.patch.object(grub.GrubConfig, "_save_grub_configuration")
    def test_update_with_apply_failure_due_grub_update(self, mock_save, *_):
        """Test update current grub config with apply error due grub update failure."""
        config = grub.GrubConfig("charm-a")
        with self.assertRaises(grub.ApplyError):
            config.update({"GRUB_TIMEOUT": "0"})

        self.assertDictEqual(config._data, EXP_GRUB_CONFIG)
        self.assertEqual(len(mock_save.mock_calls), 2)

    @mock.patch.object(grub, "is_container", return_value=False)
    @mock.patch.object(grub.subprocess, "check_call")
    @mock.patch.object(grub, "_save_config")
    @mock.patch.object(grub.GrubConfig, "_save_grub_configuration")
    def test_update(self, mock_save, mock_save_config, *_):
        """Test update current grub config."""
        exp_charm = "charm-a"
        exp_config = {"GRUB_TIMEOUT": "0"}
        config = grub.GrubConfig(exp_charm)
        config.update(exp_config)

        self.assertDictEqual(config._data, EXP_GRUB_CONFIG)
        mock_save.assert_called_once()
        mock_save_config.assert_called_once_with(self.tmp_dir / exp_charm, exp_config)
