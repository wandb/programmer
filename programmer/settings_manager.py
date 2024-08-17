import os

SETTINGS_DIR = ".programmer"
SETTINGS_FILE = "settings"
DEFAULT_SETTINGS = {
    "weave_logging": "local",
    "git_tracking": "off"
}
ALLOWED_VALUES = {
    "weave_logging": ["off", "local", "cloud"],
    "git_tracking": ["off", "on"]
}


class SettingsError(Exception):
    pass


class SettingsManager:
    @staticmethod
    def initialize_settings():
        """
        Ensure that the settings directory and file exist, and populate missing settings with defaults.
        """
        if not os.path.exists(SETTINGS_DIR):
            os.makedirs(SETTINGS_DIR)
        settings_path = os.path.join(SETTINGS_DIR, SETTINGS_FILE)
        if not os.path.exists(settings_path):
            SettingsManager.write_default_settings()
        else:
            SettingsManager.validate_and_complete_settings()

    @staticmethod
    def validate_and_complete_settings():
        """
        Validate the settings file format and complete it with default values if necessary.
        """
        settings_path = os.path.join(SETTINGS_DIR, SETTINGS_FILE)
        with open(settings_path, "r") as f:
            lines = f.readlines()

        settings = {}
        for line in lines:
            if "=" not in line:
                raise SettingsError(f"Malformed settings line: '{line.strip()}'.\n"
                                    f"Please ensure each setting is in 'key=value' format.\n"
                                    f"Settings file location: {settings_path}")
            key, value = line.strip().split("=", 1)
            if key in ALLOWED_VALUES and value not in ALLOWED_VALUES[key]:
                raise SettingsError(f"Invalid value '{value}' for setting '{key}'. Allowed values are: {ALLOWED_VALUES[key]}\n"
                                    f"Settings file location: {settings_path}")
            settings[key] = value

        # Add missing default settings
        for key, default_value in DEFAULT_SETTINGS.items():
            if key not in settings:
                settings[key] = default_value

        # Rewrite the settings file with complete settings
        with open(settings_path, "w") as f:
            for key, value in settings.items():
                f.write(f"{key}={value}\n")

    @staticmethod
    def write_default_settings():
        """
        Write the default settings to the settings file.
        """
        settings_path = os.path.join(SETTINGS_DIR, SETTINGS_FILE)
        with open(settings_path, "w") as f:
            for key, value in DEFAULT_SETTINGS.items():
                f.write(f"{key}={value}\n")

    @staticmethod
    def get_setting(key):
        """
        Retrieve a setting's value by key.
        """
        settings_path = os.path.join(SETTINGS_DIR, SETTINGS_FILE)
        if not os.path.exists(settings_path):
            return None
        with open(settings_path, "r") as f:
            for line in f.readlines():
                if line.startswith(key):
                    return line.split("=")[1].strip()
        return None

    @staticmethod
    def set_setting(key, value):
        """
        Set a setting's value by key, validating allowed values.
        """
        settings_path = os.path.join(SETTINGS_DIR, SETTINGS_FILE)
        if key in ALLOWED_VALUES and value not in ALLOWED_VALUES[key]:
            raise SettingsError(f"Invalid value '{value}' for setting '{key}'. Allowed values are: {ALLOWED_VALUES[key]}\n"
                                f"Settings file location: {settings_path}")

        lines = []
        found = False
        if os.path.exists(settings_path):
            with open(settings_path, "r") as f:
                lines = f.readlines()
            for i, line in enumerate(lines):
                if line.startswith(key):
                    lines[i] = f"{key}={value}\n"
                    found = True
                    break
        if not found:
            lines.append(f"{key}={value}\n")
        with open(settings_path, "w") as f:
            f.writelines(lines)
