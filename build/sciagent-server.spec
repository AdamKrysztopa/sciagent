# PyInstaller spec for sciagent-server binary (SCI-0604).
# Build: uv run pyinstaller build/sciagent-server.spec \
#          --distpath build/dist --workpath build/work --clean

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# Collect the full agt package (uvicorn.run receives it as a string so
# PyInstaller cannot auto-detect it via import analysis).
agt_submodules = collect_submodules("agt")
agt_datas = collect_data_files("agt")
# spellchecker loads en.json.gz via pkgutil.get_data at import time; must be bundled.
spell_datas = collect_data_files("spellchecker")

hidden_imports = agt_submodules + [
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "anyio._backends._asyncio",
    "anyio._backends._trio",
    "pydantic_settings",
    "pydantic_settings.env_settings",
    "pydantic_settings.main",
    "structlog",
    "structlog.stdlib",
    "fastapi",
    "slowapi",
    "slowapi.extension",
]

a = Analysis(
    ["../src/agt/server.py"],
    pathex=["../src"],
    binaries=[],
    datas=agt_datas + spell_datas,
    hiddenimports=hidden_imports,
    hookspath=["./hooks"],
    runtime_hooks=[],
    excludes=["streamlit", "matplotlib", "PIL", "tkinter", "keybert", "pytest", "vcrpy"],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz, a.scripts, a.binaries, a.zipfiles, a.datas, [],
    name="sciagent-server",
    debug=False,
    strip=False,
    upx=True,
    console=True,
)
