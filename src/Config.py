import platform
import os
import json
import sys
import ctypes
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

def load_config():
    default_root = ""
    steam_path = ""
    detected = False
    if platform.system() == "Windows":
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\\Valve\\Steam") as key:
                steam_path = winreg.QueryValueEx(key, "SteamPath")[0]
                detected = True
        except Exception:
            steam_path = r"C:\Program Files (x86)\Steam"
        default_root = os.path.join(steam_path, "steamapps", "common", "SonicRacingCrossWorlds")
    elif platform.system() == "Linux":
        default_root = os.path.join(os.path.expanduser("~"), ".local", "share", "Steam", "steamapps", "common",
                                    "SonicRacingCrossWorlds")
    default_mods = os.path.join(default_root, "UNION", "Content", "Paks", "~mods")
    os.makedirs(default_mods, exist_ok=True)
    config_data = None
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config_data = json.load(f)
        except Exception:
            pass
    if config_data and isinstance(config_data, dict):
        root = config_data.get("game_root", default_root)
        steam_detected = config_data.get("steam_detected", False)
        enabled_mods = config_data.get("enabled_mods", {})
        show_cmd_logs = config_data.get("show_cmd_logs", False)
        # If mods_folder is missing after first launch, default to a subfolder in the config dir.
        # This prevents asking the user repeatedly. The prompt should only be for the very first run.
        return {
            "mods_folder": config_data.get("mods_folder", os.path.join(CONFIG_DIR, "mods")),
            "game_root": root,
            "game_mods_folder": os.path.join(root, "UNION", "Content", "Paks", "~mods"),
            "ue4ss_mods_folder": os.path.join(root, "UNION", "Binaries", "Win64", "ue4ss", "Mods"),
            "ue4ss_logic_mods_folder": os.path.join(root, "UNION", "Content", "Paks", "LogicMods"),
            "enabled_mods": enabled_mods,
            "show_cmd_logs": show_cmd_logs,
            "steam_detected": steam_detected,
            "mod_priority": config_data.get("mod_priority", []),
            "window_size": config_data.get("window_size", "580x700")
        }
    else:
        # First launch: save detected Steam path info
        cfg = {
            "mods_folder": default_mods_folder(),
            "game_root": default_root,
            "game_mods_folder": default_mods,
            "ue4ss_mods_folder": os.path.join(default_root, "UNION", "Binaries", "Win64", "ue4ss", "Mods"),
            "ue4ss_logic_mods_folder": os.path.join(default_root, "UNION", "Content", "Paks", "LogicMods"),
            "enabled_mods": {},
            "show_cmd_logs": False,
            "steam_detected": detected,
            "mod_priority": [],
            "window_size": "580x700"
        }
        save_config(cfg)
        return cfg

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
