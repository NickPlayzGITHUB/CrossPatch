import threading
import socket
import sys
import os

from PySide6.QtWidgets import QApplication
from CrossPatch import CrossPatchWindow
import Util
import Config # This will now set up config paths on import

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
