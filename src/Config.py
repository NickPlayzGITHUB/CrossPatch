import platform
import os
import json
import sys
import ctypes
import re
if platform.system() == "Windows": import winreg
from tkinter import filedialog, messagebox, Tk

def get_config_dir():
    """
    Determines the appropriate directory for configuration files.
    If CROSSPATCH_PORTABLE=1 is set, it uses the current working directory.
    Otherwise, it uses platform-specific app data locations.
    """
    if os.environ.get("CROSSPATCH_PORTABLE") == "1":
        return os.getcwd()

    if platform.system() == "Windows":
        return os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "CrossPatch")
    else: # Linux and other UNIX-like systems
        return os.path.join(os.path.expanduser("~"), ".config", "CrossPatch")

CONFIG_DIR = get_config_dir()
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
os.makedirs(CONFIG_DIR, exist_ok=True)

def default_mods_folder():
    """Determines the default mods folder path based on operating mode."""
    if os.environ.get("CROSSPATCH_PORTABLE") == "1":
        path = os.path.join(os.getcwd(), "mods")
        os.makedirs(path, exist_ok=True)
        return path
    
    root = Tk()
    root.withdraw()
    messagebox.showinfo("Welcome to CrossPatch!", "Please select a folder to store your mods.\n Note: this is NOT your ~mods folder", parent=root)
    folder = filedialog.askdirectory(title="Select a folder for your mods", parent=root)
    root.destroy()
    if not folder:
        sys.exit("No mods folder selected. Exiting.")
    return folder

def default_game_folder():
    """Tries to auto-detect the game folder, and prompts the user if it fails."""
    default_root = ""
    detected = False
    if platform.system() == "Windows":
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\\Valve\\Steam") as key:
                steam_path = winreg.QueryValueEx(key, "SteamPath")[0]
                default_root = _find_game_in_steam_libraries(steam_path)
                detected = bool(default_root)
        except FileNotFoundError:
            print("Steam registry key not found.")
    elif platform.system() == "Linux":
        # This path is still a guess, but it's a common one.
        linux_path = os.path.join(os.path.expanduser("~"), ".local", "share", "Steam", "steamapps", "common", "SonicRacingCrossWorlds")
        if os.path.isdir(linux_path):
            default_root = linux_path
            detected = True

    if not default_root:
        # Auto-detection failed, prompt the user.
        root = Tk()
        root.withdraw()
        messagebox.showinfo("Setup: Game Directory", "Could not automatically find Sonic Racing Crossworlds. Please select the game's installation folder.", parent=root)
        folder = filedialog.askdirectory(title="Select Sonic Racing Crossworlds Folder", parent=root)
        root.destroy()
        if not folder:
            sys.exit("No game folder selected. Exiting.")
        default_root = folder
    return default_root, detected

_original_stdout = sys.stdout
_original_stderr = sys.stderr
_console_streams = None

def show_console():
    global _console_streams
    try:
        if ctypes.windll.kernel32.AllocConsole():
            _console_streams = (
                open("CONOUT$", "w", buffering=1),
                open("CONOUT$", "w", buffering=1)
            )
            sys.stdout = _console_streams[0]
            sys.stderr = _console_streams[1]
            print("Welcome to CrossPatch's Console logs! If you're a regular user there's really no point in having this enabled\nYou should only use this for debugging purposes, serves no other purpose really")
    except Exception as e:
        print(f"Failed to show console: {e}")
        sys.stdout = _original_stdout
        sys.stderr = _original_stderr

def hide_console():
    global _console_streams
    try:
        sys.stdout = _original_stdout
        sys.stderr = _original_stderr
        if _console_streams:
            try:
                _console_streams[0].close()
                _console_streams[1].close()
            except:
                pass
            _console_streams = None
        ctypes.windll.kernel32.FreeConsole()
    except Exception as e:
        print(f"Failed to hide console: {e}")

def _find_game_in_steam_libraries(steam_path, app_id="2486820"):
    """Parses Steam's library file to find the game in any library folder."""
    library_folders_vdf = os.path.join(steam_path, "steamapps", "libraryfolders.vdf")
    app_manifest_file = f"appmanifest_{app_id}.acf"
    
    # List of all potential library paths, starting with the main one
    library_paths = [steam_path]

    if os.path.exists(library_folders_vdf):
        try:
            with open(library_folders_vdf, "r", encoding="utf-8") as f:
                # This regex finds all "path" values in the VDF file
                found_paths = re.findall(r'"path"\s+"([^"]+)"', f.read())
                for path in found_paths:
                    library_paths.append(path.replace("\\\\", "\\"))
        except Exception as e:
            print(f"Could not parse libraryfolders.vdf: {e}")

    # Now, search for the appmanifest file in each library
    for library_path in library_paths:
        manifest_path = os.path.join(library_path, "steamapps", app_manifest_file)
        if os.path.exists(manifest_path):
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    # Find the "installdir" value
                    match = re.search(r'"installdir"\s+"([^"]+)"', content)
                    if match:
                        game_folder_name = match.group(1)
                        game_path = os.path.join(library_path, "steamapps", "common", game_folder_name)
                        if os.path.isdir(game_path):
                            print(f"Found game at: {game_path}")
                            return game_path
            except Exception as e:
                print(f"Error reading manifest file {manifest_path}: {e}")
    
    print("Game not found in any Steam library.")
    return "" # Return empty if not found

def load_config():
    """Loads the configuration from disk, creating a default one only if it doesn't exist."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config_data = json.load(f)
            # Basic validation to ensure it's a dictionary
            if isinstance(config_data, dict):
                return config_data
        except json.JSONDecodeError as e:
            # The file is corrupt. Back it up and notify the user.
            print(f"Error loading config.json: {e}")
            corrupt_path = os.path.join(CONFIG_DIR, "config.json.corrupt")
            try:
                os.rename(CONFIG_FILE, corrupt_path)
                messagebox.showwarning(
                    "Configuration Error",
                    f"Your config.json file was corrupt and has been backed up to:\n{corrupt_path}\n\nA new configuration will be created."
                )
            except Exception as backup_error:
                messagebox.showerror(
                    "Configuration Error",
                    f"Your config.json file is corrupt, but could not be backed up.\n\nError: {backup_error}"
                )
        except Exception as e:
            print(f"An unexpected error occurred while loading config: {e}")

    # If we reach here, it means no valid config exists. Create a new one.
    print("No valid configuration found. Creating a new one.")
    try:
        default_root, detected = default_game_folder()
        cfg = {
            "mods_folder": default_mods_folder(),
            "game_root": default_root,
            "game_mods_folder": os.path.join(default_root, "UNION", "Content", "Paks", "~mods"),
            "ue4ss_mods_folder": os.path.join(default_root, "UNION", "Binaries", "Win64", "ue4ss", "Mods"),
            "ue4ss_logic_mods_folder": os.path.join(default_root, "UNION", "Content", "Paks", "LogicMods"),
            "enabled_mods": {},
            "show_cmd_logs": False,
            "steam_detected": detected,
            "mod_priority": [],
            "window_size": "580x720"
        }
        save_config(cfg)
        return cfg
    except SystemExit as e:
        # This happens if the user cancels a folder dialog during first-time setup.
        sys.exit(f"Configuration setup cancelled. {e}")

def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)

config = load_config()

def register_url_protocol():
    """
    Registers the crosspatch:// URL protocol in the Windows Registry.
    This allows the app to be launched from a web link.
    """
    if platform.system() != "Windows":
        print("URL protocol registration is only supported on Windows.")
        return

    try:
        # The command to execute. It differs between dev and packaged app.
        if getattr(sys, 'frozen', False): # Packaged app
            command = f'"{sys.executable}" "%1"'
        else: # Development (running with python.exe)
            script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src', 'Main.py'))
            command = f'"{sys.executable}" "{script_path}" "%1"'

        # Registry path
        key_path = r"Software\Classes\crosspatch"
        
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            winreg.SetValue(key, None, winreg.REG_SZ, "URL:CrossPatch Protocol")
            winreg.SetValueEx(key, "URL Protocol", 0, winreg.REG_SZ, "")
            with winreg.CreateKey(key, r"shell\open\command") as command_key:
                winreg.SetValue(command_key, None, winreg.REG_SZ, command)
        print("Successfully registered crosspatch:// URL protocol.")
    except Exception as e:
        print(f"Error: Could not register URL protocol. Please try running as administrator. Details: {e}")
