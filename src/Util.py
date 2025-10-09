import os
import json
import shutil
import subprocess
import urllib.request
import webbrowser
import platform

from UpdatePrompt import UpdatePromptWindow

from Constants import UPDATE_URL, APP_VERSION

'''
Code from:
https://coderslegacy.com/tkinter-center-window-on-screen/
'''
def center_window(root):
    root.update_idletasks()
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
 
    x = (screen_width/2) - (root.winfo_width()/2)
    y = (screen_height/2) - (root.winfo_height()/2)
 
    root.geometry('%dx%d+%d+%d' % (root.winfo_width(), root.winfo_height(), x, y))

def fetch_remote_version():
    print("Fetching version.txt")
    try:
        with urllib.request.urlopen(UPDATE_URL, timeout=5) as resp:
            return resp.read().decode("utf-8").strip()
    except Exception:
        return None

def is_newer_version(local, remote):
    def to_nums(v):
        return [int(x) for x in v.split(".")]
    lv, rv = to_nums(local), to_nums(remote)
    length = max(len(lv), len(rv))
    lv += [0] * (length - len(lv))
    rv += [0] * (length - len(rv))
    return rv > lv

def check_for_updates(root):
    print("Checking for updates...")
    remote = fetch_remote_version()
    if remote and is_newer_version(APP_VERSION, remote):
        print(f"CrossPatch {APP_VERSION} is outdated, Latest Version is {remote}")
        root.after(0, lambda: show_update_prompt(root, remote))

def show_update_prompt(root, remote):
    UpdatePromptWindow(root, remote)

def list_mod_folders(path):
    if not os.path.isdir(path):
        return []
    try:
        return sorted(
            [d for d in os.listdir(path)
             if os.path.isdir(os.path.join(path, d))],
            key=str.lower
        )
    except Exception:
        return []


def read_mod_info(mod_path):
    info_file = os.path.join(mod_path, "info.json")
    if os.path.exists(info_file):
        try:
            return json.load(open(info_file, "r", encoding="utf-8"))
        except Exception:
            return {}
    return {}


def get_game_mods_folder(cfg):
    return os.path.join(
        cfg["game_root"],
        "UNION",
        "Content",
        "Paks",
        "~mods"
    )


def clean_mods_folder(cfg):  # enhanced refresh
    dst = get_game_mods_folder(cfg)
    if not os.path.isdir(dst):
        return

    for filename in os.listdir(dst):
        file_path = os.path.join(dst, filename)
        try:
            if os.path.isfile(file_path):
                os.remove(file_path)
        except Exception as e:
            print(f"Error removing {filename}: {e}")

def launch_game():
    if platform.system() == "Windows":
        print(
            f"Attempting to launch Sonic Racing CrossWorlds...")  # Removed the EXE check since too many people were having issues, idk why that was even a thing after I made the game launch from steam instead of the exe
        webbrowser.open("steam://run/2486820")
    elif platform.system() == "Linux":
        subprocess.Popen(["steam", "steam://rungameid/2486820"])
    print("Opening Crossworlds...")


def disable_mod(mod_name, cfg):
    print(f"disabled {mod_name}")
    dst = get_game_mods_folder(cfg)
    if not os.path.isdir(dst):
        return
    src = os.path.join(cfg["mods_folder"], mod_name)
    to_remove = {
        f for _, _, files in os.walk(src)
        for f in files
        if f.lower() != "info.json"
    }
    for f in to_remove:
        path = os.path.join(dst, f)
        if os.path.exists(path):
            os.remove(path)
    cfg["enabled_mods"][mod_name] = False


def enable_mod(mod_name, cfg):
    print(f"enabled {mod_name}")
    src = os.path.join(cfg["mods_folder"], mod_name)
    dst = get_game_mods_folder(cfg)
    os.makedirs(dst, exist_ok=True)
    for root, _, files in os.walk(src):
        for f in files:
            if f.lower() == "info.json":
                continue
            shutil.copy2(
                os.path.join(root, f),
                os.path.join(dst, f)
            )
    cfg["enabled_mods"][mod_name] = True
    print(f"{mod_name} files copied to {dst}")
