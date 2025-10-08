import os
import json
import shutil
import subprocess
import urllib.request
import webbrowser
import platform
import re
import tkinter as tk
from tkinter import messagebox

from UpdatePrompt import UpdatePromptWindow

from Constants import UPDATE_URL, APP_VERSION
from DownloadManager import DownloadManager
from Config import CONFIG_DIR

# --- Handle optional archive dependencies for UE4SS install ---
try:
    import py7zr
    PY7ZR_SUPPORT = True
except ImportError:
    PY7ZR_SUPPORT = False

try:
    import rarfile
    RARFILE_SUPPORT = True
except ImportError:
    RARFILE_SUPPORT = False

'''
Code from:
https://coderslegacy.com/tkinter-center-window-on-screen/
'''
def center_window(root):
    if platform.system() == "Windows":
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
            with open(info_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            # If info.json is corrupt, treat it as if it doesn't exist
            pass

    # info.json does not exist, so we auto-detect and create it.
    mod_name = os.path.basename(mod_path)
    detected_type = "pak"  # Default type

    # Auto-detection logic
    logic_mods_path = os.path.join(mod_path, "LogicMods")
    script_path = os.path.join(mod_path, "Scripts")

    if os.path.isdir(logic_mods_path):
        detected_type = "ue4ss-logic"
    elif os.path.isdir(script_path):
        detected_type = "ue4ss-script"

    print(f"Auto-detected '{mod_name}' as type: {detected_type}")

    new_info = {
        "name": mod_name,
        "version": "1.0",
        "author": "Unknown",
        "mod_type": detected_type
    }

    try:
        with open(info_file, "w", encoding="utf-8") as f:
            json.dump(new_info, f, indent=2)
    except Exception as e:
        print(f"Error creating info.json for {mod_name}: {e}")

    return new_info


def get_game_mods_folder(cfg):
    return os.path.join(
        cfg["game_root"],
        "UNION",
        "Content",
        "Paks",
        "~mods"
    )


def clean_mods_folder(cfg):  # enhanced refresh
    # Clean Pak mods folder
    pak_dst = get_game_mods_folder(cfg)
    if os.path.isdir(pak_dst):
        # This regex matches folders that start with a number and a dot, e.g., "0.MyMod"
        # This ensures we only delete folders managed by CrossPatch.
        managed_folder_pattern = re.compile(r"^\d+\..+")
        for item in os.listdir(pak_dst):
            item_path = os.path.join(pak_dst, item)
            try:
                if os.path.isdir(item_path) and managed_folder_pattern.match(item):
                    shutil.rmtree(item_path)
            except Exception as e:
                print(f"Error removing directory {item} from pak mods: {e}")

    # Clean UE4SS Logic mods folder
    ue4ss_logic_dst = cfg.get("ue4ss_logic_mods_folder")
    if ue4ss_logic_dst and os.path.isdir(ue4ss_logic_dst):
        known_mods = list_mod_folders(cfg["mods_folder"])
        for item in os.listdir(ue4ss_logic_dst):
            if item in known_mods:
                item_path = os.path.join(ue4ss_logic_dst, item)
                try:
                    shutil.rmtree(item_path)
                except Exception as e:
                    print(f"Error removing directory {item} from logic mods: {e}")

    # Clean UE4SS mods folder
    ue4ss_dst = cfg.get("ue4ss_mods_folder")
    if ue4ss_dst and os.path.isdir(ue4ss_dst):
        # Get a list of all known mod folder names from the source mods folder
        known_mods = list_mod_folders(cfg["mods_folder"])
        for item in os.listdir(ue4ss_dst):
            # Only remove folders that are recognized as mods managed by CrossPatch
            if item in known_mods:
                item_path = os.path.join(ue4ss_dst, item)
                try:
                    # Check if it's a UE4SS mod before removing
                    mod_info = read_mod_info(os.path.join(cfg["mods_folder"], item))
                    if mod_info.get("mod_type", "pak").startswith("ue4ss") and os.path.isdir(item_path):
                        # For UE4SS mods, just delete the enabled.txt file to disable them.
                        enabled_txt_path = os.path.join(item_path, "enabled.txt")
                        if os.path.exists(enabled_txt_path):
                            os.remove(enabled_txt_path)
                except Exception as e:
                    print(f"Error disabling UE4SS mod {item}: {e}")

def remove_mod_from_game_folders(mod_name, cfg):
    """
    Explicitly removes a single mod's installed files from both pak and UE4SS directories.
    This is used when a mod's type is changed to ensure no orphaned files are left.
    """
    print(f"Performing targeted removal of '{mod_name}' from game folders...")

    # Remove from Pak mods folder (looks for prefixed folders like "0.MyMod")
    pak_dst = get_game_mods_folder(cfg)
    if os.path.isdir(pak_dst):
        # Regex to find the priority-prefixed folder for this specific mod
        managed_folder_pattern = re.compile(r"^\d+\." + re.escape(mod_name) + "$")
        for item in os.listdir(pak_dst):
            item_path = os.path.join(pak_dst, item)
            if os.path.isdir(item_path) and managed_folder_pattern.match(item):
                try:
                    print(f"Removing old pak installation: {item_path}")
                    shutil.rmtree(item_path)
                except Exception as e:
                    print(f"Error removing directory {item_path}: {e}")

    # Remove from UE4SS script and logic mods folders
    ue4ss_script_path = os.path.join(cfg.get("ue4ss_mods_folder", ""), mod_name)
    if os.path.isdir(ue4ss_script_path):
        print(f"Removing old UE4SS script installation: {ue4ss_script_path}")
        shutil.rmtree(ue4ss_script_path)

    ue4ss_logic_path = os.path.join(cfg.get("ue4ss_logic_mods_folder", ""), mod_name)
    if os.path.isdir(ue4ss_logic_path):
        print(f"Removing old UE4SS logic installation: {ue4ss_logic_path}")
        shutil.rmtree(ue4ss_logic_path)

def launch_game():
    if platform.system() == "Windows":
        print(
            f"Attempting to launch Sonic Racing CrossWorlds...")  # Removed the EXE check since too many people were having issues, idk why that was even a thing after I made the game launch from steam instead of the exe
        webbrowser.open("steam://run/2486820")
    elif platform.system() == "Linux":
        subprocess.Popen(["steam", "steam://rungameid/2486820"])
    print("Opening Crossworlds...")


def _ensure_ue4ss_installed(cfg, root_window):
    """Checks if UE4SS is installed and installs it if not."""
    win64_path = os.path.join(cfg["game_root"], "UNION", "Binaries", "Win64")
    ue4ss_folder = os.path.join(win64_path, "ue4ss")
    dwmapi_dll = os.path.join(win64_path, "dwmapi.dll")

    if os.path.isdir(ue4ss_folder) and os.path.exists(dwmapi_dll):
        print("UE4SS is already installed.")
        return True # UE4SS is present

    # UE4SS is not installed, so we need to download it.
    if not messagebox.askyesno(
        "UE4SS Not Found",
        "A UE4SS-based mod requires UE4SS to be installed.\n\n"
        "CrossPatch can automatically download and install it for you. "
        "Do you want to proceed?",
        parent=root_window
    ):
        messagebox.showwarning("Mod Not Enabled", "The mod was not enabled because UE4SS is required.", parent=root_window)
        return False

    ue4ss_url = "https://gamebanana.com/tools/20876"
    print(f"UE4SS not found. Downloading from {ue4ss_url}")

    # We can use a temporary DownloadManager for this one-off task.
    # We'll use a temporary folder for the download to keep things clean.
    temp_download_dir = os.path.join(CONFIG_DIR, "temp_downloads")
    os.makedirs(temp_download_dir, exist_ok=True)
    
    try:
        dm = DownloadManager(root_window, temp_download_dir)
        # This is a synchronous call for simplicity, as the mod can't be enabled until this is done.
        dm.download_and_extract_to(ue4ss_url, win64_path)
        print("UE4SS installation completed.")
        shutil.rmtree(temp_download_dir, ignore_errors=True)
        return True
    except Exception as e:
        messagebox.showerror("UE4SS Installation Failed", f"Failed to download or install UE4SS. The mod will not be enabled.\n\nError: {e}", parent=root_window)
        shutil.rmtree(temp_download_dir, ignore_errors=True)
        return False

def enable_mod(mod_name, cfg, priority):
    mod_info = read_mod_info(os.path.join(cfg["mods_folder"], mod_name))
    mod_type = mod_info.get("mod_type", "pak") # Default to 'pak' if not specified

    src = os.path.join(cfg["mods_folder"], mod_name)

    if mod_type == "ue4ss-script":
        dst = os.path.join(cfg["ue4ss_mods_folder"], mod_name)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        # For UE4SS Script mods, copy files and create 'enabled.txt'
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns('info.json'), dirs_exist_ok=True)
        with open(os.path.join(dst, "enabled.txt"), "w") as f:
            f.write("") # The file just needs to exist.
    elif mod_type == "ue4ss-logic":
        dst = os.path.join(cfg["ue4ss_logic_mods_folder"], mod_name)
        os.makedirs(dst, exist_ok=True)
        # For Logic mods, copy the contents directly. They are removed entirely on disable.
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns('info.json'), dirs_exist_ok=True)
    else: # Default to pak mod behavior
        # Handles 'pak' mods. Create a folder with priority prefix, e.g., "0.MyMod"
        prefixed_mod_name = f"{priority:03d}.{mod_name}"
        dst = os.path.join(get_game_mods_folder(cfg), prefixed_mod_name)
        os.makedirs(dst, exist_ok=True)
        for root, _, files in os.walk(src):
            rel_root = os.path.relpath(root, src)
            target_root = os.path.join(dst, rel_root) if rel_root != "." else dst
            os.makedirs(target_root, exist_ok=True)
            for f in files:
                if f.lower() == "info.json":
                    continue
                shutil.copy2(
                    os.path.join(root, f),
                    os.path.join(target_root, f)
                )

    cfg["enabled_mods"][mod_name] = True

def enable_mod_with_ui(mod_name, cfg, priority, root_window):
    """Wrapper for enable_mod that handles UI interactions like the UE4SS check."""
    mod_info = read_mod_info(os.path.join(cfg["mods_folder"], mod_name))
    mod_type = mod_info.get("mod_type", "pak")

    # If it's a UE4SS mod, ensure UE4SS is installed first.
    if mod_type.startswith("ue4ss"):
        if not _ensure_ue4ss_installed(cfg, root_window):
            # User cancelled or installation failed, so we abort enabling this mod.
            cfg["enabled_mods"][mod_name] = False # Ensure it's marked as disabled
            return

    print(f"Enabling {mod_name} (type: {mod_type}) with priority {priority}")
    enable_mod(mod_name, cfg, priority)
