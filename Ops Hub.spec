# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['launcher.py'],
    pathex=[],
    binaries=[],
    datas=[('core', 'core'), ('modules', 'modules'), ('framework', 'framework'), ('gui', 'gui'), ('assets', 'assets')],
    hiddenimports=[
        # python-docx
        'docx', 'docx.enum.table', 'docx.enum.text', 'docx.oxml', 'docx.oxml.ns', 'docx.shared',
        # openpyxl
        'openpyxl', 'openpyxl.drawing.image', 'openpyxl.styles', 'openpyxl.utils',
        # PIL / Pillow
        'PIL', 'PIL.Image', 'PIL.ImageTk', 'PIL.ImageDraw', 'PIL.ImageFont', 'PIL.ExifTags',
        # reportlab
        'reportlab', 'reportlab.lib', 'reportlab.lib.colors', 'reportlab.lib.pagesizes',
        'reportlab.lib.styles', 'reportlab.lib.units', 'reportlab.lib.enums', 'reportlab.lib.fonts',
        'reportlab.platypus', 'reportlab.pdfgen', 'reportlab.pdfbase', 'reportlab.pdfbase.pdfmetrics',
        'reportlab.pdfbase.ttfonts',
        # matplotlib
        'matplotlib', 'matplotlib.figure', 'matplotlib.backends.backend_tkagg', 'matplotlib.ticker',
        # tkcalendar + babel
        'tkcalendar', 'babel.numbers',
        # tkinter submodules
        'tkinter.colorchooser', 'tkinter.filedialog', 'tkinter.messagebox', 'tkinter.ttk',
        # stdlib
        'sqlite3', 'mailbox', 'csv', 'configparser', 'ctypes', 'email', 'hashlib',
        'json', 'queue', 'uuid', 'getpass',
        # misc third-party
        'pypdf', 'pdfplumber', 'pdfminer', 'pdfminer.high_level', 'send2trash',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Ops Hub',
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
    icon=['assets\\ops_hub.ico'],
)
