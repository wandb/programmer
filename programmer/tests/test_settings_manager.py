import os
import pytest
from programmer.settings_manager import SettingsManager, SETTINGS_DIR, SETTINGS_FILE, SettingsError, DEFAULT_SETTINGS

@pytest.fixture(scope="function")
def setup_and_teardown_settings():
    """Fixture to set up and tear down a temporary settings directory for testing."""
    test_dir = SETTINGS_DIR
    test_file = os.path.join(test_dir, SETTINGS_FILE)
    if not os.path.exists(test_dir):
        os.makedirs(test_dir)
    yield test_file
    if os.path.exists(test_file):
        os.remove(test_file)
    if os.path.exists(test_dir):
        os.rmdir(test_dir)


def test_initialize_settings_creates_file_with_defaults(setup_and_teardown_settings):
    test_file = setup_and_teardown_settings
    SettingsManager.initialize_settings()
    assert os.path.exists(test_file)
    with open(test_file, "r") as f:
        settings = f.read().strip()
    expected_settings = "\n".join(f"{key}={value}" for key, value in DEFAULT_SETTINGS.items())
    assert settings == expected_settings


def test_get_setting(setup_and_teardown_settings):
    SettingsManager.initialize_settings()
    for key, value in DEFAULT_SETTINGS.items():
        assert SettingsManager.get_setting(key) == value


def test_set_setting_updates_existing(setup_and_teardown_settings):
    SettingsManager.initialize_settings()
    SettingsManager.set_setting("weave_logging", "cloud")
    assert SettingsManager.get_setting("weave_logging") == "cloud"


def test_set_setting_adds_new(setup_and_teardown_settings):
    SettingsManager.initialize_settings()
    SettingsManager.set_setting("new_setting", "value")
    assert SettingsManager.get_setting("new_setting") == "value"


def test_validate_and_complete_settings_raises_error_on_malformed_line(setup_and_teardown_settings):
    with open(setup_and_teardown_settings, "w") as f:
        f.write("malformed_line\n")
    with pytest.raises(SettingsError):
        SettingsManager.validate_and_complete_settings()


def test_validate_and_complete_settings_adds_missing_defaults(setup_and_teardown_settings):
    with open(setup_and_teardown_settings, "w") as f:
        f.write("weave_logging=local\n")  # Missing git_tracking
    SettingsManager.validate_and_complete_settings()
    assert SettingsManager.get_setting("git_tracking") == "off"


def test_set_setting_raises_error_on_invalid_value(setup_and_teardown_settings):
    SettingsManager.initialize_settings()
    with pytest.raises(SettingsError):
        SettingsManager.set_setting("weave_logging", "invalid_value")

    with pytest.raises(SettingsError):
        SettingsManager.set_setting("git_tracking", "invalid_value")
