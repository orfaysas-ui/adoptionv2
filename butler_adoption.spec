# butler_adoption.spec

block_cipher = None

a = Analysis(
    ['launcher_adoption.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('utils.py', '.'),
        ('adoption_2.py', '.'),
        ('hotel_list.csv', '.'),
    ],
    hiddenimports=[
        'pandas',
        'openpyxl',
        'openpyxl.cell._writer',
        'numpy',
        'babel.numbers',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['streamlit'],
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
    name='ButlerAdoption',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
