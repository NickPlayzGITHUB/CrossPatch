import threading
from CrossPatch import CrossPatchWindow
import Util

if __name__ == "__main__":    
    app = CrossPatchWindow()
    threading.Thread(target=lambda: Util.check_for_updates(app), daemon=True).start()
    app.mainloop()
