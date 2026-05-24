@echo off
chcp 65001 >nul
echo.
echo  ╔══════════════════════════════════════════════╗
echo  ║         Assistente IA — Build Script         ║
echo  ╚══════════════════════════════════════════════╝
echo.

:: Verifica se npm está disponível
where npm >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERRO] npm não encontrado. Instale o Node.js e tente novamente.
    pause
    exit /b 1
)

:: Verifica se python está disponível
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERRO] Python não encontrado. Instale o Python 3.10+ e tente novamente.
    pause
    exit /b 1
)

:: ── Passo 1: Build do React ───────────────────────────────────────────────
echo [1/3] Construindo interface React (npm run build)...
call npm run build
if %errorlevel% neq 0 (
    echo [ERRO] Falha no build do React. Verifique os erros acima.
    pause
    exit /b 1
)
echo [OK] Build do React concluido em: dist\
echo.

:: ── Passo 2: Instalar dependências Python ────────────────────────────────
echo [2/3] Instalando dependencias Python...
pip install -r requirements.txt pyinstaller --quiet
if %errorlevel% neq 0 (
    echo [ERRO] Falha ao instalar dependencias Python.
    pause
    exit /b 1
)
echo [OK] Dependencias instaladas.
echo.

:: ── Passo 3: Compilar executável ─────────────────────────────────────────
echo [3/3] Compilando executavel Windows com PyInstaller...
pyinstaller assistente_ia.spec --clean --noconfirm
if %errorlevel% neq 0 (
    echo [ERRO] Falha na compilacao com PyInstaller.
    pause
    exit /b 1
)

echo.
echo  ╔══════════════════════════════════════════════╗
echo  ║  Build concluido com sucesso!                ║
echo  ║  Executavel: dist\AssistenteIA\AssistenteIA.exe ║
echo  ╚══════════════════════════════════════════════╝
echo.
pause
