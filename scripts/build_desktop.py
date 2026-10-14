"""
build_desktop.py — Script de automação do empacotamento desktop (PyInstaller / PyWebView).
Empacota a UI React compilada e o runtime do pipeline num pacote executável standalone.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
UI_DIR = ROOT_DIR / "UI"
DIST_DIR = UI_DIR / "dist"
PIPELINE_DIR = ROOT_DIR / "pipeline"
SPEC_FILE = UI_DIR / "assistente_ia.spec"


def build_react_frontend() -> None:
    print("[1/3] Compilando frontend React (npm run build)...")
    npm_cmd = "npm.cmd" if sys.platform == "win32" else "npm"
    result = subprocess.run([npm_cmd, "run", "build"], cwd=UI_DIR, check=False)
    if result.returncode != 0:
        print("[ERRO] Falha na compilação do React.", file=sys.stderr)
        sys.exit(result.returncode)
    print("[OK] Frontend compilado em:", DIST_DIR)


def run_pyinstaller_bundle() -> None:
    print("[2/3] Gerando executável com PyInstaller...")
    cmd = [
        "uv",
        "run",
        "--project",
        str(PIPELINE_DIR),
        "--extra",
        "desktop",
        "pyinstaller",
        str(SPEC_FILE),
        "--clean",
        "--noconfirm",
    ]
    result = subprocess.run(cmd, cwd=UI_DIR, check=False)
    if result.returncode != 0:
        print("[ERRO] Falha no empacotamento com PyInstaller.", file=sys.stderr)
        sys.exit(result.returncode)
    print("[OK] PyInstaller concluiu com sucesso.")


def verify_bundle() -> None:
    print("[3/3] Verificando integridade dos binários gerados...")
    exe_path = DIST_DIR / "AssistenteIA" / "AssistenteIA.exe"
    if not exe_path.exists():
        print(f"[ERRO] Executável não encontrado em: {exe_path}", file=sys.stderr)
        sys.exit(1)
    size_mb = exe_path.stat().st_size / (1024 * 1024)
    print(f"[OK] Executável verificado: {exe_path} ({size_mb:.2f} MB)")


def main() -> None:
    print("==================================================")
    print("  Escólio — Build & Packaging Desktop Release  ")
    print("==================================================")
    build_react_frontend()
    run_pyinstaller_bundle()
    verify_bundle()
    print("\n[SUCESSO] Pacote Desktop gerado com sucesso!")


if __name__ == "__main__":
    main()
