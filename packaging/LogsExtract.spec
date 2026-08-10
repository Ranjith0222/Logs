# -*- mode: python ; coding: utf-8 -*-
# Build on Windows (from repo root), same layout as Policywise_Generator:
#   .venv\  build\  dist\LogsExtract.exe
#
#   build.bat
#   -or-
#   pyinstaller packaging/LogsExtract.spec --noconfirm --clean --distpath dist --workpath build

block_cipher = None

a = Analysis(
    ['../src/logs/desktop/app.py'],
    pathex=['../src'],
    binaries=[],
    datas=[],
    hiddenimports=[
        'logs',
        'logs.desktop',
        'logs.desktop.app',
        'logs.desktop.service',
        'logs.ruleset',
        'logs.extract',
        'logs.scraper',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'fastapi',
        'uvicorn',
        'httpx',
        'logs.web',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='LogsExtract',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
