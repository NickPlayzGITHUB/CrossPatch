import os
import json
import subprocess
from typing import Dict, Optional, List


def _possible_parser_paths() -> List[str]:
    base = os.path.dirname(os.path.dirname(__file__))
    return [
        os.path.join(base, "tools", "CrossPatchParser", "bin", "Release", "net8.0", "publish", "CrossPatchParser.exe"),
        os.path.join(base, "tools", "CrossPatchParser", "bin", "Release", "net8.0", "CrossPatchParser.exe"),
        os.path.join(base, "tools", "CrossPatchParser", "bin", "Release", "net7.0", "publish", "CrossPatchParser.exe"),
        os.path.join(base, "tools", "CrossPatchParser", "bin", "Release", "net7.0", "CrossPatchParser.exe"),
        os.path.join(base, "tools", "CrossPatchParser", "bin", "Release", "net8.0", "publish", "CrossPatchParser"),
        # Framework-dependent (dll) locations - run via `dotnet <dll>` if found
        os.path.join(base, "tools", "CrossPatchParser", "bin", "Release", "net8.0", "publish", "CrossPatchParser.dll"),
        os.path.join(base, "tools", "CrossPatchParser", "bin", "Release", "net8.0", "CrossPatchParser.dll"),
        os.path.join(base, "tools", "CrossPatchParser", "bin", "Release", "net7.0", "publish", "CrossPatchParser.dll"),
        os.path.join(base, "tools", "CrossPatchParser", "bin", "Release", "net7.0", "CrossPatchParser.dll"),
    ]


def run_parser(mod_path: str, name: Optional[str] = None, author: Optional[str] = None,
               version: Optional[str] = None, mount_point: Optional[str] = None,
               parser_path: Optional[str] = None) -> Dict:
    """
    Runs the CrossPatchParser tool to analyze pak files in a mod folder.
    
    Args:
        mod_path: Path to the mod folder containing pak file(s)
        name: Optional mod name
        author: Optional mod author
        version: Optional mod version
        mount_point: Optional mount point override
        parser_path: Optional path to parser executable (to avoid searching multiple times)
        author: Optional mod author
        version: Optional mod version
        mount_point: Optional mount point for pak files

    Returns:
        Dict containing the parsed information
    """
    possible_paths = _possible_parser_paths()
    parser_path = None
    for p in possible_paths:
        if os.path.exists(p):
            parser_path = p
            break

    if not parser_path:
        raise FileNotFoundError(
            "CrossPatchParser executable not found. Please run the build script to publish the tool for your platform. "
            "On Linux/macOS ensure you either publish a self-contained executable or have the .NET runtime installed to run the DLL via 'dotnet'."
        )

    # Determine how to invoke the parser: if it's a .dll, use `dotnet <dll>`;
    # otherwise attempt to execute the found file directly. This covers
    # both framework-dependent and self-contained publishes across OSes.
    if parser_path.lower().endswith('.dll'):
        cmd = ["dotnet", parser_path, "--path", mod_path]
    else:
        cmd = [parser_path, "--path", mod_path]
    if name:
        cmd.extend(["--mod-name", name])
    if author:
        cmd.extend(["--mod-author", author])
    if version:
        cmd.extend(["--mod-version", version])
    if mount_point:
        cmd.extend(["--mount-point", mount_point])

    try:
        # Prevent hangs by adding a timeout (seconds). 30s is a reasonable default
        # for analyzing a small set of pak files; adjust if needed.
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=30)
        out = result.stdout.strip()
        if not out:
            # If stdout is empty, include stderr for diagnostics
            raise RuntimeError(f"Parser produced no output. Stderr: {result.stderr.strip()}")
        try:
            return json.loads(out)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Failed to parse tool output: {e}; output starts with: {out[:200]!r}")
    except subprocess.TimeoutExpired:
        raise RuntimeError("Parser timed out after 30 seconds")
    except subprocess.CalledProcessError as e:
        stderr = e.stderr or ""
        raise RuntimeError(f"Parser failed: {stderr}")
def self_contained_parser_available() -> bool:
    """Return True if a self-contained (native) parser executable exists for this platform.

    This checks the same search locations as `run_parser` but only considers
    non-.dll files (executables). On Unix-like systems it also checks the
    executable bit.
    """
    for p in _possible_parser_paths():
        if p.lower().endswith('.dll'):
            continue
        if os.path.exists(p):
            # On POSIX, ensure the file is executable
            try:
                if os.name == 'posix':
                    if os.access(p, os.X_OK):
                        return True
                else:
                    # On Windows, existence is sufficient for .exe
                    return True
            except Exception:
                # If access check fails, fall back to existence
                return True
    return False

def generate_mod_pak_manifest(mod_path: str) -> Dict:
    """
    Analyzes all pak files in a mod folder and generates a detailed manifest.

    Args:
        mod_path: Path to the mod folder containing pak file(s)

    Returns:
        Dict containing details about all pak files in the mod
    """
    # Fast path: if the mod already has info.json with pak_data, reuse it
    try:
        info_path = os.path.join(mod_path, "info.json")
        if os.path.exists(info_path):
            try:
                with open(info_path, "r", encoding="utf-8") as f:
                    info = json.load(f)
                pak_data = info.get('pak_data')
                if pak_data:
                    return pak_data
            except Exception:
                # Fall back to running parser if info.json malformed
                pass

        result = run_parser(mod_path)
        pak = result.get('pak_data', {})

        # Persist to info.json to speed up future runs
        try:
            if os.path.exists(info_path):
                with open(info_path, "r", encoding="utf-8") as f:
                    info = json.load(f)
            else:
                info = {}
            info['pak_data'] = pak
            with open(info_path, "w", encoding="utf-8") as f:
                json.dump(info, f, indent=2)
        except Exception:
            # Non-fatal - ignore persistence failures
            pass

        return pak
    except Exception as e:
        print(f"Warning: Pak analysis failed: {e}")
        return {'pak_files': [], 'total_files': 0, 'total_size': 0}