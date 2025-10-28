import threading
import socket
import sys
import os

from PySide6.QtWidgets import QApplication
from CrossPatch import CrossPatchWindow
import Util
import Config # This will now set up config paths on import
import PakInspector
import webbrowser
import subprocess
import platform

SINGLE_INSTANCE_PORT = 38471 # A random, hopefully unused port
if __name__ == "__main__":
    # Try to bind to a port to enforce a single instance
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", SINGLE_INSTANCE_PORT))
    except OSError:
        # Port is already in use, another instance is running.
        # Send the command-line argument to the running instance.
        if len(sys.argv) > 1:
            try:
                client_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                client_sock.connect(("127.0.0.1", SINGLE_INSTANCE_PORT))
                # Send the URL argument
                client_sock.sendall(sys.argv[1].encode('utf-8'))
                client_sock.close()
                print("Sent URL to running instance.")
            except Exception as e:
                print(f"Could not send URL to running instance: {e}")
        # Exit this new instance
        sys.exit(0)

    # This is the primary instance.
    Config.register_url_protocol()

    app = QApplication(sys.argv)
    # Apply a dark theme
    try:
        import qdarktheme
        app.setStyleSheet(qdarktheme.load_stylesheet("dark"))
    except ImportError:
        print("qdarktheme not found. Using default system theme.")

    # --- Ensure .NET 8 runtime is available for the pak parser ---
    def _has_dotnet_8():
        """Return True if a .NET runtime 8.x is present (checked via `dotnet --list-runtimes`)."""
        try:
            proc = subprocess.run(["dotnet", "--list-runtimes"], capture_output=True, text=True, check=True, timeout=5)
            out = proc.stdout + proc.stderr
            # Look for Microsoft.NETCore.App 8.* or similar runtime entries
            for line in out.splitlines():
                if "Microsoft.NETCore.App" in line or "Microsoft.AspNetCore.App" in line:
                    # line format: Name Version [path]
                    parts = line.strip().split()
                    if len(parts) >= 2:
                        ver = parts[1]
                        if ver.startswith("8.") or ver.startswith("8"):
                            return True
            return False
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            return False

    # If we have a self-contained parser executable for this platform, the
    # .NET runtime is not required. Only prompt for dotnet if no native parser
    # is present.
    if not _has_dotnet_8() and not getattr(PakInspector, 'self_contained_parser_available', lambda: False)():
        # Prompt the user to install .NET 8 before proceeding. We show this
        # dialog before creating the main window so the user must choose.
        from PySide6.QtWidgets import QMessageBox

        reply = QMessageBox.question(
            None,
            "Missing .NET Runtime",
            "CrossPatch requires the .NET 8 runtime to analyze pak files.\n\nWould you like to open the .NET 8 download page now?\n\n(If you choose No, the application will exit.)",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )

        if reply == QMessageBox.Yes:
            # Open the .NET 8 runtime download page (runtime-specific) to reduce confusion.
            runtime_url = "https://dotnet.microsoft.com/en-us/download/dotnet/8.0/runtime"
            try:
                # Prefer OS-targeted pages where helpful
                if platform.system() == "Windows":
                    runtime_url = "https://dotnet.microsoft.com/en-us/download/dotnet/thank-you/runtime-desktop-8.0.21-windows-x64-installer"
                elif platform.system() == "Linux":
                    runtime_url = "https://dotnet.microsoft.com/en-us/download/dotnet/8.0/runtime"
                elif platform.system() == "Darwin":
                    runtime_url = "https://dotnet.microsoft.com/en-us/download/dotnet/8.0/runtime"
            except Exception:
                pass
            webbrowser.open(runtime_url)
        print(".NET 8 runtime not detected; exiting.")
        sys.exit(1)

    window = CrossPatchWindow(instance_socket=sock)

    # Handle initial command-line argument if app was launched with one
    if len(sys.argv) > 1:
        url = sys.argv[1]
        window.handle_protocol_url(url)

    # Start the thread that checks for app updates, unless disabled by an environment variable.
    if os.environ.get("CROSSPATCH_DISABLE_UPDATES") != "1":
        threading.Thread(target=lambda: Util.check_for_updates_pyside(window), daemon=True).start()
    else:
        print("Auto-updater is disabled via CROSSPATCH_DISABLE_UPDATES environment variable.")

    window.show()
    sys.exit(app.exec())
