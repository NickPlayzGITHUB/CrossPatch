from PyInstaller.utils.hooks import collect_submodules, is_module_satisfies


def hook(hook_api):
    """
    This hook is necessary because qdarktheme can optionally use PyQt5, PyQt6, PySide2, or PySide6.
    If multiple are installed, PyInstaller may try to bundle them all, causing a conflict.
    This ensures that if PySide6 is being used by the main app, we explicitly exclude PyQt5.
    """
    if is_module_satisfies("PySide6"):
        hook_api.add_excludes(["PyQt5", "PyQt6", "PySide2"])
    hook_api.add_datas(collect_submodules("qdarktheme", include_py_files=True))