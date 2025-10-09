import platform
import os
import json
import sys
import ctypes

from Constants import CONFIG_FILE

def default_mods_folder():
    path = os.path.join(os.getcwd(), "mods")
    print("Path: ", path)
    os.makedirs(path, exist_ok=True)
    return path

_original_stdout = sys.stdout
_original_stderr = sys.stderr
_console_streams = None

def load_config():
    default_root = ""
    if platform.system() == "Windows":
        default_root = r"C:\Program Files (x86)\Steam\steamapps\common\SonicRacingCrossWorlds"
    elif platform.system() == "Linux":
        default_root = os.path.join(os.path.expanduser("~"), ".local", "share", "Steam", "steamapps", "common",
                                    "SonicRacingCrossWorlds")
    default_mods = os.path.join(default_root, "UNION", "Content", "Paks", "~mods")
    os.makedirs(default_mods, exist_ok=True)
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                root = data.get("game_root", default_root)
                return {
                    "mods_folder": data.get("mods_folder", default_mods_folder()),
                    "game_root": root,
                    "game_mods_folder": os.path.join(root, "UNION", "Content", "Paks", "~mods"),
                    "enabled_mods": data.get("enabled_mods", {}),
                    "show_cmd_logs": data.get("show_cmd_logs", False)
                }
        except Exception:
            pass
    return {
        "mods_folder": default_mods_folder(),
        "game_root": default_root,
        "game_mods_folder": default_mods,
        "enabled_mods": {},
        "show_cmd_logs": False
    }

def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)

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
            print(
                "Welcome to CrossPatch's Console logs! If you're a regular user there's really no point in having this enabled\nYou should only use this for debugging purposes, serves no other purpose really")
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
        pass
        print(f"Failed to hide console: {e}")

config = load_config()