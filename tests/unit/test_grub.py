# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.
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


class BaseTestGrubLib(unittest.TestCase):
    def setUp(self) -> None:
        tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_dir = Path(tmp_dir.name)
        self.addCleanup(tmp_dir.cleanup)

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

    def test_registered_configs(self):
        """Test registered_configs property."""
        ...

    def test_update(self):
        """Test update current grub config."""
        ...
