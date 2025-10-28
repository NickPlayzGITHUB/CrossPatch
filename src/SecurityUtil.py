import os
import hashlib
from PySide6.QtWidgets import QMessageBox
from typing import Optional, Tuple

def verify_file_hash(file_path: str, expected_hash: Optional[str] = None) -> Tuple[bool, str]:
    """
    Verify the SHA-256 hash of a downloaded file.
    Returns (True, hash) if verification succeeds or no expected hash provided.
    Returns (False, hash) if verification fails.
    """
    if not os.path.exists(file_path):
        return (False, "")

    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        # Read file in chunks to handle large files
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    
    calculated_hash = sha256_hash.hexdigest()
    
    if expected_hash:
        return (calculated_hash.lower() == expected_hash.lower(), calculated_hash)
    return (True, calculated_hash)

def confirm_sensitive_operation(parent, operation: str, details: str) -> bool:
    """
    Show a confirmation dialog for sensitive operations like downloads and file modifications.
    Returns True if user confirms, False otherwise.
    """
    msg = QMessageBox(parent)
    msg.setIcon(QMessageBox.Warning)
    msg.setWindowTitle("Security Check")
    msg.setText(f"CrossPatch needs to {operation}")
    msg.setInformativeText(details)
    msg.setDetailedText("This operation requires modifying files on your system. CrossPatch only performs actions that you explicitly approve.")
    msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
    msg.setDefaultButton(QMessageBox.No)
    
    return msg.exec() == QMessageBox.Yes