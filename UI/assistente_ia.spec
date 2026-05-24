# assistente_ia.spec
# ─────────────────────────────────────────────────────────────────────────────
# Arquivo de configuração do PyInstaller para empacotar o Assistente IA
# como um executável Windows standalone (.exe).
#
# Como usar:
#   1. Execute: npm run build        (dentro da pasta UI)
#   2. Execute: pyinstaller assistente_ia.spec --clean
#   3. O executável estará em: dist\AssistenteIA\AssistenteIA.exe
# ─────────────────────────────────────────────────────────────────────────────

block_cipher = None

a = Analysis(
    ['main.py'],               # Script principal de entrada
    pathex=[],
    binaries=[],
    datas=[
        # Inclui o build do React (dist/) junto ao executável
        ('dist', 'dist'),
    ],
    hiddenimports=[
        'webview',
        'webview.platforms.winforms',  # Plataforma Windows (Edge WebView2)
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='AssistenteIA',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,                    # Sem janela de console (app GUI)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon='assets/icon.ico',         # Descomente e ajuste para usar ícone customizado
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AssistenteIA',              # Nome da pasta gerada em dist/
)
