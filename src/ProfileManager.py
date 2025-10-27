import Config
import copy

class ProfileManager:
    """
    Manages all operations related to mod profiles, acting as a single
    source of truth for profile data and modifications.
    """
    DEFAULT_PROFILE_NAME = "Default"

    def __init__(self, config):
        self.config = config
        self._migrate_if_needed()

    def _migrate_if_needed(self):
        """
        Checks if the config is from a pre-profile version and migrates
        the old mod settings into a 'Default' profile.
        """
        if "profiles" not in self.config or not isinstance(self.config["profiles"], dict):
            print("Migrating old config to new profile structure...")
            old_enabled_mods = self.config.pop("enabled_mods", {})
            old_mod_priority = self.config.pop("mod_priority", [])

            self.config["profiles"] = {
                self.DEFAULT_PROFILE_NAME: {
                    "enabled_mods": old_enabled_mods,
                    "mod_priority": old_mod_priority
                }
            }
            self.config["active_profile"] = self.DEFAULT_PROFILE_NAME
            self.save()

    def save(self):
        """Saves the entire configuration to disk."""
        Config.save_config(self.config)

    def get_active_profile_name(self):
        """Returns the name of the currently active profile."""
        return self.config.get("active_profile", self.DEFAULT_PROFILE_NAME)

    def get_active_profile(self):
        """Returns the dictionary of the active profile's data."""
        active_name = self.get_active_profile_name()
        # Ensure the active profile always exists
        if active_name not in self.config["profiles"]:
            self.set_active_profile(self.DEFAULT_PROFILE_NAME)
            active_name = self.DEFAULT_PROFILE_NAME
        return self.config["profiles"][active_name]

    def get_profile_names(self):
        """Returns a list of all profile names."""
        return list(self.config.get("profiles", {}).keys())

    def set_active_profile(self, name):
        """Sets the active profile."""
        if name in self.config["profiles"]:
            self.config["active_profile"] = name
            self.save()
            return True
        return False

    def create_profile(self, new_name):
        """Creates a new profile by copying the currently active one."""
        if not new_name or not new_name.strip() or new_name in self.config["profiles"]:
            return False
        
        active_profile_data = copy.deepcopy(self.get_active_profile())
        self.config["profiles"][new_name] = active_profile_data
        self.set_active_profile(new_name) # Also switches to the new profile
        self.save()
        return True

    def rename_profile(self, old_name, new_name):
        """Renames a profile."""
        if old_name == self.DEFAULT_PROFILE_NAME or not new_name or not new_name.strip() or new_name in self.config["profiles"]:
            return False
        
        self.config["profiles"][new_name] = self.config["profiles"].pop(old_name)
        if self.get_active_profile_name() == old_name:
            self.config["active_profile"] = new_name
        self.save()
        return True

    def delete_profile(self, name_to_delete):
        """Deletes a profile, ensuring the default is not deleted."""
        if name_to_delete == self.DEFAULT_PROFILE_NAME or len(self.config["profiles"]) <= 1:
            return False

        if self.get_active_profile_name() == name_to_delete:
            self.set_active_profile(self.DEFAULT_PROFILE_NAME)
        
        del self.config["profiles"][name_to_delete]
        self.save()
        return True

    def set_mod_priority(self, new_priority_list):
        """Sets the mod priority for the active profile."""
        self.get_active_profile()["mod_priority"] = new_priority_list
        self.save()

    def set_mod_enabled(self, mod_id, is_enabled):
        """Sets the enabled state for a mod in the active profile."""
        self.get_active_profile()["enabled_mods"][mod_id] = is_enabled
        self.save()

    def set_mod_configuration(self, mod_name, selections):
        """
        Sets the configuration selections for a specific mod in the active profile.
        """
        active_profile = self.get_active_profile()
        # Use setdefault to create the 'mod_configurations' dict if it doesn't exist,
        # then add the selections for the specific mod.
        active_profile.setdefault("mod_configurations", {})[mod_name] = selections
        self.save()

    def set_mod_configuration(self, mod_name, selections):
        """
        Sets the configuration selections for a specific mod in the active profile.
        """
        active_profile = self.get_active_profile()
        # Use setdefault to create the 'mod_configurations' dict if it doesn't exist,
        # then add the selections for the specific mod.
        active_profile.setdefault("mod_configurations", {})[mod_name] = selections
        self.save()