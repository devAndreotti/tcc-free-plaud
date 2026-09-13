[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [string]$Command = 'help',

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Rest
)

$ErrorActionPreference = 'Stop'

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Pipeline = Join-Path $Root 'pipeline'
$UI = Join-Path $Root 'UI'

function Show-Help {
    @'
Uso: .\fp.ps1 <comando> [args]

Comandos:
  tui     abre a TUI Textual
  menu    abre o menu terminal numerado
  app     builda o React e abre o app integrado PyWebView
  front   roda o Vite com mock de desenvolvimento
  doctor  executa diagnostico estruturado do ambiente
  bench   executa o benchmark experimental
  test    roda os testes do backend
  release gera o executavel standalone desktop (.exe e .zip)

Exemplos:
  .\fp.ps1 tui
  .\fp.ps1 menu
  .\fp.ps1 app
'@
}

function Invoke-InPipeline {
    param(
        [string]$Executable,
        [string[]]$CommandArgs
    )

    Push-Location $Pipeline
    try {
        & $Executable @CommandArgs
        $code = $LASTEXITCODE
    }
    finally {
        Pop-Location
    }
    exit $code
}

function Invoke-Npm {
    param([string[]]$CommandArgs)

    $npm = if (Get-Command npm.cmd -ErrorAction SilentlyContinue) { 'npm.cmd' } else { 'npm' }
    & $npm @CommandArgs
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}

switch ($Command.ToLowerInvariant()) {
    'tui' {
        Invoke-InPipeline 'uv' (@('run', 'free-plaud', 'tui') + $Rest)
    }
    'menu' {
        Invoke-InPipeline 'uv' (@('run', 'free-plaud', 'menu') + $Rest)
    }
    'app' {
        Invoke-Npm (@('--prefix', $UI, 'run', 'build'))
        Invoke-InPipeline 'uv' (@('run', '--extra', 'desktop', 'python', (Join-Path $UI 'main.py')) + $Rest)
    }
    { $_ -in @('front', 'dev') } {
        Invoke-Npm (@('--prefix', $UI, 'run', 'dev') + $Rest)
    }
    'doctor' {
        Invoke-InPipeline 'uv' (@('run', 'free-plaud', 'doctor') + $Rest)
    }
    'bench' {
        Invoke-InPipeline 'uv' (@('run', 'free-plaud', 'benchmark') + $Rest)
    }
    'test' {
        Invoke-InPipeline 'uv' (@('run', 'pytest') + $Rest)
    }
    'release' {
        Invoke-InPipeline 'uv' (@('run', '--extra', 'desktop', '--extra', 'audio', 'python', (Join-Path $Root 'scripts/build_desktop.py')) + $Rest)
        $zipPath = Join-Path $Root 'AssistenteIA-windows-x64.zip'
        $distFolder = Join-Path $UI 'dist/AssistenteIA'
        if (Test-Path $distFolder) {
            Compress-Archive -Path $distFolder -DestinationPath $zipPath -Force
            Write-Host "[OK] Pacote compactado gerado: $zipPath" -ForegroundColor Green
        }
    }
    { $_ -in @('help', '-h', '--help') } {
        Show-Help
    }
    default {
        Write-Error "Comando desconhecido: $Command"
        Show-Help
        exit 2
    }
}
