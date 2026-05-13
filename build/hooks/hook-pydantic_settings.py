from PyInstaller.utils.hooks import collect_submodules

hiddenimports = collect_submodules("pydantic_settings")
