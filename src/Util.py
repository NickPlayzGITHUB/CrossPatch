import os
import json
import requests
import shutil
import subprocess
import zipfile
import urllib.request
import webbrowser
import platform
import re
import sys
import threading
from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QApplication, QMessageBox

from Constants import UPDATE_URL, APP_VERSION, STEAM_APP_ID
from Config import CONFIG_DIR

class ModListFetchEvent(QEvent):
    """Custom event for when the mod list has been fetched."""
    EVENT_TYPE = QEvent.Type(QEvent.registerEventType())
    def __init__(self, mods_data):
        super().__init__(self.EVENT_TYPE)
        self.mods_data = mods_data

# --- Handle optional archive dependencies for UE4SS install ---
try:
    import py7zr
    PY7ZR_SUPPORT = True
except ImportError:
    PY7ZR_SUPPORT = False

try:
    import rarfile
    UNRAR_SUPPORT = True
except ImportError:
    UNRAR_SUPPORT = False

def is_packaged():
    """Checks if the application is running as a packaged executable."""
    return getattr(sys, 'frozen', False) or "__compiled__" in globals()

def find_assets_dir(max_up_levels=4, verbose=False):
    """
    Finds the 'assets' directory by searching from multiple candidate base paths.
    This is a robust method to handle different execution contexts like running
    from source, or as a packaged application (Nuitka, PyInstaller).
    """
    candidates = []

    if is_packaged():
        candidates.append(os.path.dirname(sys.executable))
    if hasattr(sys, "_MEIPASS"):
        candidates.append(sys._MEIPASS)
    try:
        candidates.append(os.path.dirname(os.path.abspath(sys.argv[0])))
    except Exception:
        pass
    try:
        file_dir = os.path.abspath(os.path.dirname(__file__))
        candidates.append(file_dir)
        candidates.append(os.path.abspath(os.path.join(file_dir, "..")))
    except NameError:
        pass
    candidates.append(os.getcwd())

    seen = set()
    filtered_candidates = [c for c in candidates if c and c not in seen and not seen.add(c)]

    for base in filtered_candidates:
        for up in range(max_up_levels + 1):
            check_path = os.path.abspath(os.path.join(base, *(['..'] * up)))
            assets_path = os.path.join(check_path, "assets")
            if os.path.isdir(assets_path):
                if verbose:
                    print(f"[find_assets_dir] Found assets at: {assets_path} (base='{base}', up={up})")
                return assets_path

    print("[find_assets_dir] WARNING: Could not find assets directory. Falling back to a default path.")
    return os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "assets")

def center_window_pyside(window):
    """Centers a PySide6 window on the screen. This is primarily for Windows."""
    if platform.system() != "Windows":
        return # Centering is often handled better by the WM on Linux/macOS

    screen = QApplication.primaryScreen()
    if not screen:
        return
    screen_geometry = screen.availableGeometry()
    window_geometry = window.frameGeometry()
    center_point = screen_geometry.center()
    window_geometry.moveCenter(center_point)
    window.move(window_geometry.topLeft())

def get_gb_item_details_from_url(url):
    """
    Extracts the item type (e.g., 'mods', 'sounds') and ID from a GameBanana URL.
    Returns a tuple (item_type, item_id) or (None, None).
    """
    valid_types = ["mods", "wips", "sounds", "sprays", "maps", "guis", "tools"]
    parts = url.split('/')
    
    for i, part in enumerate(parts):
        if part in valid_types:
            if i + 1 < len(parts) and parts[i+1].isdigit():
                return (part, parts[i+1]) # Returns plural form, e.g. ('sounds', '82487')

    return (None, None)

def get_gb_page_url_from_item_data(item_data):
    """Constructs a full GameBanana page URL from item data."""
    profile_url = item_data.get('_sProfileUrl')
    if profile_url:
        return f"https://gamebanana.com/{profile_url}"
    
    item_type = item_data.get('_sModelName', '').lower()
    item_id = item_data.get('_idRow')
    if item_type and item_id:
        return f"https://gamebanana.com/{item_type}s/{item_id}"
    return None

def get_gb_item_name(item_type, item_id):
    """Fetches an item's name from the GameBanana API using its type and ID."""
    if not item_type or not item_id:
        raise ValueError("Invalid item type or ID provided.")

    # API expects singular, capitalized type (e.g., "Mod", "Sound")
    api_item_type = item_type.rstrip('s').capitalize()
    api_url = f"https://gamebanana.com/apiv11/{api_item_type}/{item_id}?_csvProperties=_sName"
    
    try:
        response = requests.get(api_url, headers={'User-Agent': f'CrossPatch/{APP_VERSION}'}, timeout=5)
        response.raise_for_status()
        item_data = response.json()
        name = item_data.get('_sName')
        if not name:
            raise ValueError("Could not find item name in API response.")
        return name
    except requests.RequestException as e:
        raise ConnectionError(f"Could not connect to GameBanana API: {e}")
    except (json.JSONDecodeError, ValueError) as e:
        raise ValueError(f"Could not parse API response or find name: {e}")

def get_gb_item_name_from_url(url):
    """Convenience function to get an item's name directly from its page URL."""
    item_type, item_id = get_gb_item_details_from_url(url)
    if not item_type or not item_id:
        raise ValueError("Could not extract valid item details from the URL.")
    return get_gb_item_name(item_type, item_id)

def get_gb_item_data_from_url(url):
    """
    Fetches the full item data (including name and files) from the GameBanana API.
    """
    item_type, item_id = get_gb_item_details_from_url(url)
    if not item_type or not item_id:
        raise ValueError("Could not extract a valid item type and ID from the URL.")

    api_item_type = item_type.rstrip('s').capitalize()
    api_url = f"https://gamebanana.com/apiv11/{api_item_type}/{item_id}?_csvProperties=_sName,_aFiles,_sDescription,_sText,_aPreviewMedia"
    
    try:
        response = requests.get(api_url, headers={'User-Agent': f'CrossPatch/{APP_VERSION}'}, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        raise ConnectionError(f"Could not connect to GameBanana API: {e}")
    except json.JSONDecodeError as e:
        raise ValueError(f"Could not parse API response: {e}")

def get_gb_item_data_by_id(item_type, item_id):
    """
    Fetches the full item data (including name and files) from the GameBanana API
    using its type and ID directly.
    """
    if not item_type or not item_id:
        raise ValueError("Invalid item type or ID provided.")

    # API expects singular, capitalized type (e.g., "Mod", "Sound")
    api_item_type = item_type.rstrip('s').capitalize()
    api_url = f"https://gamebanana.com/apiv11/{api_item_type}/{item_id}?_csvProperties=_sName,_aFiles,_sDescription,_sText,_aPreviewMedia"
    
    try:
        response = requests.get(api_url, headers={'User-Agent': f'CrossPatch/{APP_VERSION}'}, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        raise ConnectionError(f"Could not connect to GameBanana API: {e}")
    except json.JSONDecodeError as e:
        raise ValueError(f"Could not parse API response: {e}")

def get_gb_mod_version(mod_page_url):
    """
    Fetches the latest version of a mod from the GameBanana API given its page URL.

    Args:
        mod_page_url (str): The full URL to the mod's GameBanana page.

    Returns:
        str: The version string (e.g., "1.1") or None if not found.
    
    Raises:
        ValueError: If the URL is invalid or details cannot be extracted.
        requests.RequestException: If there's a network-related error.
    """
    item_type, item_id = get_gb_item_details_from_url(mod_page_url)
    if not item_type or not item_id:
        raise ValueError("Could not extract valid item details from the URL.")

    api_item_type = item_type.rstrip('s').capitalize()
    api_url = f"https://gamebanana.com/apiv11/{api_item_type}/{item_id}?_csvProperties=_sVersion"
    
    headers = {'User-Agent': f'CrossPatch/{APP_VERSION}', 'Accept': 'application/json'}
    response = requests.get(api_url, headers=headers, timeout=10)
    response.raise_for_status()
    
    item_data = response.json()
    return item_data.get("_sVersion")

def get_gb_mod_list(game_id, sort='default', page=1, search_query=None, category_id=None):
    """
    Fetches a list of mods for a given game from the GameBanana API.
    """
    base_url = f"https://gamebanana.com/apiv11/Game/{game_id}/Subfeed"
    params = {
        '_sSort': sort,
        '_nPage': page,
        '_csvProperties': '_sName,_sProfileUrl,_nLikeCount,_nViewCount,_nTotalDownloads,_aSubmitter,_aPreviewMedia,_aFiles'
    }
    # The API returns a 400 Bad Request if _csvModelInclusions is present when _sSort is 'search'.
    if sort != 'search':
        params['_csvModelInclusions'] = 'Mod,Wip'

    # Per user suggestion, use _sName for searching on the Subfeed endpoint.
    if search_query:
        params['_sName'] = f"*{search_query}*"
    
    if category_id:
        params['_idCategory'] = category_id

    headers = {'User-Agent': f'CrossPatch/{APP_VERSION}', 'Accept': 'application/json'}
    print(f"[DEBUG] Fetching GB mod list. URL: {base_url}, Params: {params}")

    try:
        # Using a prepared request to easily log the full URL
        req = requests.Request('GET', base_url, params=params, headers=headers)
        prepared = req.prepare()
        print(f"[DEBUG] Full request URL: {prepared.url}")

        response = requests.get(base_url, params=params, headers=headers, timeout=15)
        print(f"[DEBUG] GB API Response Status: {response.status_code}")
        response.raise_for_status()
        data = response.json()
        print(f"[DEBUG] GB API Response JSON: {json.dumps(data, indent=2)}")
        return data.get('_aRecords', []), data.get('_aMetadata', {})
    except requests.RequestException as e:
        raise ConnectionError(f"Could not connect to GameBanana Subfeed API: {e}")

def get_gb_top_mods(game_id, page=1):
    """Fetches Top mods for a game from the GameBanana API."""
    base_url = f"https://gamebanana.com/apiv11/Game/{game_id}/TopSubs"
    params = {
        '_nPage': page,
        '_csvProperties': '_sName,_sProfileUrl,_nLikeCount,_nViewCount,_nTotalDownloads,_aSubmitter,_aPreviewMedia,_aFiles'
    }
    headers = {'User-Agent': f'CrossPatch/{APP_VERSION}', 'Accept': 'application/json'}
    print(f"[DEBUG] Fetching GB Top mods. URL: {base_url}, Params: {params}")
    try:
        response = requests.get(base_url, params=params, headers=headers, timeout=15)
        response.raise_for_status()
        # This endpoint returns a simple list. We return it and a basic metadata object.
        # The caller will know this endpoint doesn't support pagination.
        return response.json(), {'_bIsComplete': True}
    except requests.RequestException as e:
        raise ConnectionError(f"Could not connect to GameBanana TopSubs API: {e}")

def get_gb_featured_mods(game_id, page=1):
    """Fetches Featured mods for a game from the GameBanana API."""
    base_url = "https://gamebanana.com/apiv11/Util/List/Featured"
    params = {
        '_nPage': page,
        '_idGameRow': game_id,
        '_csvProperties': '_sName,_sProfileUrl,_nLikeCount,_nViewCount,_nTotalDownloads,_aSubmitter,_aPreviewMedia,_aFiles'
    }
    headers = {'User-Agent': f'CrossPatch/{APP_VERSION}', 'Accept': 'application/json'}
    print(f"[DEBUG] Fetching GB Featured mods. URL: {base_url}, Params: {params}")
    try:
        response = requests.get(base_url, params=params, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()
        # This endpoint returns a dictionary with _aRecords and _aMetadata.
        # We return both for the caller to handle pagination.
        return data.get('_aRecords', []), data.get('_aMetadata', {})
    except requests.RequestException as e:
        raise ConnectionError(f"Could not connect to GameBanana Featured API: {e}")

def get_gb_spotlight_mods(game_id, page=1):
    """Fetches Community Spotlight mods for a game from the GameBanana API."""
    base_url = f"https://gamebanana.com/apiv11/Game/{game_id}/CommunitySpotlight"
    params = {
        '_nPage': page,
        '_csvProperties': '_sName,_sProfileUrl,_nLikeCount,_nViewCount,_nTotalDownloads,_aSubmitter,_aPreviewMedia,_aFiles'
    }
    headers = {'User-Agent': f'CrossPatch/{APP_VERSION}', 'Accept': 'application/json'}
    print(f"[DEBUG] Fetching GB Spotlight mods. URL: {base_url}, Params: {params}")
    try:
        response = requests.get(base_url, params=params, headers=headers, timeout=15)
        response.raise_for_status()
        # This endpoint returns a dict with a single key (e.g., "Mod") containing the list.
        data = response.json()
        # The response is a dict with a single key (e.g., "Mod") containing the list
        if isinstance(data, dict) and len(data) == 1:
            return list(data.values())[0]
        # Sometimes it might just be a list
        elif isinstance(data, list):
            return data
        else:
            print(f"[DEBUG] Unexpected Spotlight API response format: {data}")
            return []

    except requests.RequestException as e:
        raise ConnectionError(f"Could not connect to GameBanana Spotlight API: {e}")

def fetch_specialized_lists(game_id, sort, page):
    """Helper to call specialized list endpoints and normalize their output."""
    if sort == "Featured":
        mods, metadata = get_gb_featured_mods(game_id, page)
    elif sort == "Community Spotlight":
        mods, metadata = get_gb_spotlight_mods(game_id, page), {'_bIsComplete': True} # No pagination
    else: # Default to "Top"
        mods, metadata = get_gb_top_mods(game_id, page)
    return mods, metadata


def fetch_remote_version():
    print("Fetching remote version from GitHub")
    try:
        with requests.get(UPDATE_URL, timeout=5) as resp:
            return resp.json()
    except Exception:
        return None

def is_newer_version(local, remote):
    # Ensure we're not comparing None or empty strings
    local = local or "0"
    remote = remote or "0"

    def to_nums(v):
        # Clean the version string: remove leading 'v' and any other non-numeric/non-dot characters
        # This handles versions like 'v1.0', '1.0-beta', etc.
        cleaned_v = re.sub(r'[^0-9.]', '', str(v))
        return [int(x) for x in cleaned_v.split(".") if x.isdigit()]
    lv, rv = to_nums(local), to_nums(remote) # No need to check for None here anymore
    length = max(len(lv), len(rv))
    lv += [0] * (length - len(lv))
    rv += [0] * (length - len(rv))
    return rv > lv

def check_for_updates_pyside(parent_window):
    print("Checking for updates...")
    remote_info = fetch_remote_version()
    if not remote_info:
        return

    remote_version = remote_info.get("tag_name")
    if remote_version and is_newer_version(APP_VERSION, remote_version):
        print(f"CrossPatch {APP_VERSION} is outdated, Latest Version is {remote_version}")
        # The parent window must have a signal to handle this from a non-GUI thread.
        if hasattr(parent_window, 'update_check_finished'):
            parent_window.update_check_finished.emit(remote_version, remote_info)

def show_update_prompt_pyside(parent, remote_version, remote_info):
    from Updater import Updater # Local import to avoid circular dependency
    reply = QMessageBox.question(
        parent,
        "Update Available",
        f"A new version of CrossPatch is available!\n\n"
        f"  Your Version: {APP_VERSION}\n"
        f"  Latest Version: {remote_version}\n\n"
        "Would you like to download and install it now?",
    )
    if reply == QMessageBox.Yes:
        Updater(parent, remote_info).start_update()

def synchronize_priority_with_disk(current_priority, mods_on_disk):
    """
    Synchronizes the mod priority list with the mods actually present on the disk.
    - Removes mods from the priority list that are no longer on disk.
    - Appends newly found mods to the end of the priority list.
    - Preserves the order of existing mods.
    """
    # Remove mods that are no longer on disk
    synced_priority = [mod for mod in current_priority if mod in mods_on_disk]
    # Add new mods that are not in the priority list yet
    for mod in mods_on_disk:
        if mod not in synced_priority:
            synced_priority.append(mod)
    return synced_priority

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

    # info.json does not exist or is corrupt. Auto-detect type and return a default dict.
    # The calling function will be responsible for saving it.
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
    return {
        "name": mod_name,
        "version": "1.0",
        "author": "Unknown",
        "mod_type": detected_type
    }

def discover_mod_configuration(mod_path):
    """
    Discovers a mod's configuration by scanning its subdirectories.
    A subdirectory is considered a configuration 'category' if it contains
    at least two subfolders, each with a 'desc.ini' file.
    
    Returns:
        A dictionary representing the configuration, or None.
        Example: {'Models': {'Bass_AI': {'name': 'Bass AI', 'desc': '...'}, ...}}
    """
    from ModConfigDialog import read_desc_ini # Local import
    discovered_config = {}

    if not os.path.isdir(mod_path):
        return None

    for category_name in os.listdir(mod_path):
        category_path = os.path.join(mod_path, category_name)
        if not os.path.isdir(category_path):
            continue

        options = {}
        for option_name in os.listdir(category_path):
            option_path = os.path.join(category_path, option_name)
            desc_ini_path = os.path.join(option_path, 'desc.ini')
            if os.path.isdir(option_path) and os.path.exists(desc_ini_path):
                ini_data = read_desc_ini(desc_ini_path)
                if ini_data:
                    options[option_name] = ini_data
        
        # A valid category must have at least two configurable options
        if len(options) >= 2:
            discovered_config[category_name] = options

    return discovered_config if discovered_config else None


def _apply_mod_configuration(mod_install_path, mod_info, profile_data):
    """Renames files within an installed mod folder based on configuration."""
    config = mod_info.get("configuration")
    if not config:
        return

    # This function is no longer needed with the new copy-on-select logic.
    if True:
        return

    mod_name = os.path.basename(mod_install_path)
    mod_configs = profile_data.get("mod_configurations", {}).get(mod_name, {})
    
    for category, options in config.items():
        # Default to the first option if none is selected for the category
        selected_option_folder = mod_configs.get(category, next(iter(options)))
        
        for option_folder_name in options.keys():
            is_enabled = (option_folder_name == selected_option_folder)
            source_option_path = os.path.join(mod_install_path, category, option_folder_name)
            
            if not os.path.isdir(source_option_path):
                continue

            for filename in os.listdir(source_option_path):
                # Skip the description file itself
                if filename.lower() == 'desc.ini':
                    continue
                
                source_file = os.path.join(source_option_path, filename)
                dest_file = os.path.join(mod_install_path, filename)
                disabled_dest_file = f"{dest_file}_disabled"

                if is_enabled:
                    # If this is the selected option, ensure its files are enabled
                    if os.path.exists(disabled_dest_file) and os.path.basename(disabled_dest_file) == f"{filename}_disabled":
                         os.rename(disabled_dest_file, dest_file)
                else:
                    # If this is NOT the selected option, ensure its files are disabled
                    if os.path.exists(dest_file):
                        os.rename(dest_file, disabled_dest_file)

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
        # This regex matches folders that start with 3+ digits and a dot, e.g., "000.MyMod"
        # This ensures we only delete folders managed by CrossPatch.
        managed_folder_pattern = re.compile(r"^\d{3,}\..+")
        for item in os.listdir(pak_dst):
            item_path = os.path.join(pak_dst, item)
            try:
                if os.path.isdir(item_path) and managed_folder_pattern.search(item):
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
                    if mod_info.get("mod_type") == "ue4ss-script" and os.path.isdir(item_path):
                        # For UE4SS script mods, we must remove the entire folder to ensure
                        # a clean re-installation on refresh, preventing orphaned files.
                        shutil.rmtree(item_path)
                except Exception as e:
                    print(f"Error disabling UE4SS mod {item}: {e}")

def remove_mod_from_game_folders(mod_name, cfg):
    """
    Explicitly removes a single mod's installed files from both pak and UE4SS directories.
    This is used when a mod's type is changed to ensure no orphaned files are left.
    """
    print(f"Performing targeted removal of '{mod_name}' from game folders...")

    # Read the mod's info to determine its type for accurate removal.
    mod_info = read_mod_info(os.path.join(cfg["mods_folder"], mod_name))
    mod_type = mod_info.get("mod_type", "pak")

    # Remove from Pak mods folder (looks for prefixed folders like "0.MyMod")
    if mod_type == "pak":
        pak_dst = get_game_mods_folder(cfg)
        if os.path.isdir(pak_dst):
            # Regex to find the priority-prefixed folder for this specific mod
            managed_folder_pattern = re.compile(r"^\d{3,}\." + re.escape(mod_name) + "$")
            for item in os.listdir(pak_dst):
                item_path = os.path.join(pak_dst, item)
                if os.path.isdir(item_path) and managed_folder_pattern.match(item):
                    try:
                        print(f"Removing pak installation: {item_path}")
                        shutil.rmtree(item_path)
                    except Exception as e:
                        print(f"Error removing directory {item_path}: {e}")

    # Remove from UE4SS script mods folder
    elif mod_type == "ue4ss-script":
        ue4ss_script_path = os.path.join(cfg.get("ue4ss_mods_folder", ""), mod_name)
        if os.path.isdir(ue4ss_script_path):
            print(f"Removing UE4SS script installation: {ue4ss_script_path}")
            shutil.rmtree(ue4ss_script_path)

    # Remove from UE4SS logic mods folder
    elif mod_type == "ue4ss-logic":
        ue4ss_logic_path = os.path.join(cfg.get("ue4ss_logic_mods_folder", ""), mod_name)
        if os.path.isdir(ue4ss_logic_path):
            print(f"Removing UE4SS logic installation: {ue4ss_logic_path}")
            shutil.rmtree(ue4ss_logic_path)

def launch_game():
    if platform.system() == "Windows":
        print(
            f"Attempting to launch Sonic Racing CrossWorlds...")  # Removed the EXE check since too many people were having issues, idk why that was even a thing after I made the game launch from steam instead of the exe
        webbrowser.open(f"steam://run/{STEAM_APP_ID}")
    elif platform.system() == "Linux":
        subprocess.Popen(["steam", f"steam://rungameid/{STEAM_APP_ID}"])
    print("Opening Crossworlds...")


def _ensure_ue4ss_installed(cfg, root_window):
    from src.DownloadManager import DownloadManager # Local import to break circular dependency

    """Checks if UE4SS is installed and installs it if not."""
    win64_path = os.path.join(cfg["game_root"], "UNION", "Binaries", "Win64")
    ue4ss_folder = os.path.join(win64_path, "ue4ss")
    dwmapi_dll = os.path.join(win64_path, "dwmapi.dll")

    if os.path.isdir(ue4ss_folder) and os.path.exists(dwmapi_dll):
        print("UE4SS is already installed.")
        return True # UE4SS is present

    # UE4SS is not installed, so we need to download it.
    reply = QMessageBox.question(
        root_window,
        "UE4SS Not Found",
        "A UE4SS-based mod requires UE4SS to be installed.\n\n"
        "CrossPatch can automatically download and install it for you. "
        "Do you want to proceed?",
    )
    if reply != QMessageBox.Yes:
        QMessageBox.warning(root_window, "Mod Not Enabled", "The mod was not enabled because UE4SS is required.")
        return False

    ue4ss_url = "https://gamebanana.com/tools/20876"
    print(f"UE4SS not found. Downloading from {ue4ss_url}")

    # We can use a temporary DownloadManager for this one-off task.
    # We'll use a temporary folder for the download to keep things clean.
    temp_download_dir = os.path.join(CONFIG_DIR, "temp_downloads")
    os.makedirs(temp_download_dir, exist_ok=True)
    
    try:
        # This needs to be a synchronous operation for this specific case.
        # We'll create a dummy on_complete event to wait for.
        completion_event = threading.Event()
        dm = DownloadManager(root_window, temp_download_dir, on_complete=completion_event.set)
        # The download_mod_from_url method doesn't exist in the PySide version,
        # let's use the more generic download_specific_file after getting item data.
        item_data = get_gb_item_data_from_url(ue4ss_url)
        file_to_download = max(item_data.get('_aFiles', []), key=lambda f: f.get('_nFilesize', 0))
        dm.download_specific_file(file_to_download, item_data.get('_sName', 'UE4SS'), extract_path_override=win64_path)
        completion_event.wait() # Block until download/extract is finished
        print("UE4SS installation completed.")
        shutil.rmtree(temp_download_dir, ignore_errors=True)
        return True
    except Exception as e:
        QMessageBox.critical(root_window, "UE4SS Installation Failed", f"Failed to download or install UE4SS. The mod will not be enabled.\n\nError: {e}")
        shutil.rmtree(temp_download_dir, ignore_errors=True)
        return False

def enable_mod(mod_name, cfg, priority, profile_data):
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
        # Discover file-based configuration
        file_config = discover_mod_configuration(src)
        if file_config:
            mod_info['configuration'] = file_config # Add to in-memory info

        # Handles 'pak' mods. Create a folder with priority prefix, e.g., "0.MyMod"
        prefixed_mod_name = f"{priority:03d}.{mod_name}"
        dst = os.path.join(get_game_mods_folder(cfg), prefixed_mod_name)
        os.makedirs(dst, exist_ok=True)

        # If we have a file-based config, we need to copy files from the option folders
        if file_config:
            mod_configs = profile_data.get("mod_configurations", {}).get(mod_name, {})
            for category, options in file_config.items():
                # Default to the first option if none is selected for the category
                selected_option_folder = mod_configs.get(category, next(iter(options.keys()), None))

                if selected_option_folder:
                    option_path = os.path.join(src, category, selected_option_folder)
                    print(f"Copying selected option: '{category}/{selected_option_folder}'")
                    shutil.copytree(option_path, dst, dirs_exist_ok=True)
        
        # Copy all other files from the root of the mod folder
        for root, dirs, files in os.walk(src):
            rel_root = os.path.relpath(root, src)
            target_root = os.path.join(dst, rel_root) if rel_root != "." else dst
            for f in files:
                if f.lower() == "info.json":
                    continue
                shutil.copy2(
                    os.path.join(root, f),
                    os.path.join(target_root, f)
                )
            # Stop the walk from going into the category directories we already handled
            if file_config:
                dirs[:] = [d for d in dirs if d not in file_config]
            break # Only copy from top-level


    profile_data["enabled_mods"][mod_name] = True

def enable_mod_with_ui_pyside(mod_name, cfg, priority, root_window, profile_data):
    """Wrapper for enable_mod that handles UI interactions like the UE4SS check."""
    mod_info = read_mod_info(os.path.join(cfg["mods_folder"], mod_name))
    mod_type = mod_info.get("mod_type", "pak")

    # If it's a UE4SS mod, ensure UE4SS is installed first.
    if mod_type.startswith("ue4ss"):
        if not _ensure_ue4ss_installed(cfg, root_window):
            # User cancelled or installation failed, so we abort enabling this mod.
            profile_data["enabled_mods"][mod_name] = False # Ensure it's marked as disabled
            return

    print(f"Enabling {mod_name} (type: {mod_type}) with priority {priority}")
    enable_mod(mod_name, cfg, priority, profile_data)

def enable_mods_from_priority(priority_list, enabled_mods_dict, cfg, root_window, profile_data):
    """
    Iterates through the master priority list and enables mods that are marked as enabled,
    assigning them a priority based on their position in the list.
    """
    # This counter is only for PAK mods to ensure they are prefixed correctly.
    enabled_pak_mod_count = 0
    for mod_name in priority_list:
        if enabled_mods_dict.get(mod_name, False):
            mod_info = read_mod_info(os.path.join(cfg["mods_folder"], mod_name))
            mod_type = mod_info.get("mod_type", "pak")

            # The priority number is only relevant for pak mods.
            priority_for_mod = enabled_pak_mod_count if mod_type == "pak" else 0
            enable_mod_with_ui_pyside(mod_name, cfg, priority_for_mod, root_window, profile_data)
            if mod_type == "pak":
                enabled_pak_mod_count += 1

def extract_archive(archive_path, dest_path, progress_signal=None):
    """
    Extracts an archive to a destination path and handles nested folders.

    Args:
        archive_path (str): The path to the archive file.
        dest_path (str): The destination directory for extraction.
        progress_signal (Signal, optional): A PySide6 signal to emit progress updates.
    """
    print(f"Starting extraction of '{os.path.basename(archive_path)}' to '{dest_path}'")
    # Ensure the destination directory exists and is empty for a clean extraction
    if os.path.isdir(dest_path):
        print(f"Destination '{dest_path}' exists. Removing for clean extraction.")
        shutil.rmtree(dest_path)
    os.makedirs(dest_path, exist_ok=True)

    archive_format = os.path.splitext(archive_path)[1].lower()
    print(f"Detected archive format: {archive_format}")

    if progress_signal: progress_signal.emit("Extracting...")

    if archive_format == '.zip':
        print("Using zipfile to extract.")
        with zipfile.ZipFile(archive_path, 'r') as z_ref:
            z_ref.extractall(dest_path)
    elif archive_format == '.7z' and PY7ZR_SUPPORT:
        print("Using py7zr to extract.")
        with py7zr.SevenZipFile(archive_path, 'r') as z_ref:
            z_ref.extractall(path=dest_path)
    elif archive_format == '.rar' and UNRAR_SUPPORT:
        print("Using unrar to extract.")
        # Check for a bundled unrar executable in the assets folder first
        assets_dir = find_assets_dir()
        unrar_tool_name = "UnRAR.exe" if platform.system() == "Windows" else "unrar"
        bundled_tool_path = os.path.join(assets_dir, unrar_tool_name)

        if os.path.exists(bundled_tool_path):
            print(f"Found bundled unrar tool at: {bundled_tool_path}")
            rarfile.UNRAR_TOOL = bundled_tool_path
        else:
            # Fallback to default behavior (searching PATH for 'unrar')
            rarfile.UNRAR_TOOL = "unrar"

        with rarfile.RarFile(archive_path) as rf:
            rf.extractall(path=dest_path)
    else:
        raise NotImplementedError(f"Unsupported archive format: {archive_format}. Please install the required library if available.")

    print("Initial extraction complete.")

    # --- Handle archives with a single nested folder ---
    print("Checking for nested folder structure...")
    items = os.listdir(dest_path)
    if len(items) == 1 and os.path.isdir(os.path.join(dest_path, items[0])):
        print("Single nested folder detected. Correcting structure...")
        nested_folder_path = os.path.join(dest_path, items[0])
        for item_name in os.listdir(nested_folder_path):
            shutil.move(os.path.join(nested_folder_path, item_name), dest_path)
        os.rmdir(nested_folder_path)
        print(f"Corrected nested folder structure for '{os.path.basename(dest_path)}'.")
