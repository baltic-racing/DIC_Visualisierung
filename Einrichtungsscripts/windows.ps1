# Windows PowerShell 5.1 compatible. Dot-source for offline tests; no work on import.
param([switch]$Setup, [switch]$Launch)

function ConvertTo-NativeArgument([string]$Value) {
    # Windows CommandLineToArgvW / C runtime quoting, including trailing slashes.
    '"' + [regex]::Replace([regex]::Replace($Value, '(\\*)"', '$1$1\"'), '(\\+)$', '$1$1') + '"'
}

function Invoke-Native {
    param([string]$File, [string[]]$Arguments = @(), [int]$Timeout = 30,
          [string]$Directory = $script:ProjectRoot, [hashtable]$Environment = @{})
    $info = New-Object System.Diagnostics.ProcessStartInfo
    $info.FileName = $File
    $info.Arguments = ($Arguments | ForEach-Object { ConvertTo-NativeArgument $_ }) -join ' '
    $info.WorkingDirectory = $Directory
    $info.UseShellExecute = $false
    $info.CreateNoWindow = $true
    $info.RedirectStandardOutput = $true
    $info.RedirectStandardError = $true
    $info.StandardOutputEncoding = [System.Text.Encoding]::UTF8
    $info.StandardErrorEncoding = [System.Text.Encoding]::UTF8
    $info.EnvironmentVariables['PYTHONIOENCODING'] = 'utf-8'
    foreach ($key in $Environment.Keys) { $info.EnvironmentVariables[$key] = $Environment[$key] }
    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $info
    try {
        [void]$process.Start()
        $stdout = $process.StandardOutput.ReadToEndAsync()
        $stderr = $process.StandardError.ReadToEndAsync()
        $watch = [System.Diagnostics.Stopwatch]::StartNew()
        $lastProgress = 0
        while (-not $process.WaitForExit(1000)) {
            if ($watch.Elapsed.TotalSeconds -ge $Timeout) {
                $process.Kill()
                throw "Zeitlimit fuer $File erreicht. Einrichtung beendet; ggf. noch geoeffnetes Installationsfenster schliessen und erneut versuchen."
            }
            if ($Timeout -gt 60 -and $watch.Elapsed.TotalSeconds - $lastProgress -ge 20) {
                Write-Host '  Vorgang laeuft noch ...'
                $lastProgress = $watch.Elapsed.TotalSeconds
            }
        }
        # Installer children may inherit output handles. Do not wait forever
        # after their parent exits, even if a child keeps a pipe open.
        $readers = [System.Threading.Tasks.Task]::WhenAll([System.Threading.Tasks.Task[]]@($stdout, $stderr))
        if (-not $readers.Wait(5000)) { throw "Ausgabe von $File bleibt blockiert. Offene Installationsfenster schliessen und erneut versuchen." }
        [pscustomobject]@{ Code = $process.ExitCode; Out = $stdout.GetAwaiter().GetResult(); Err = $stderr.GetAwaiter().GetResult() }
    } finally { $process.Dispose() }
}

function Find-Python {
    $candidates = @()
    # Registered installations also work immediately after installation, before
    # Explorer/PATH have been refreshed. Avoid Windows Store execution aliases.
    foreach ($key in @('HKCU:\Software\Python\PythonCore', 'HKLM:\Software\Python\PythonCore', 'HKLM:\Software\WOW6432Node\Python\PythonCore')) {
        if (Test-Path $key) {
            foreach ($version in (Get-ChildItem $key -ErrorAction SilentlyContinue | Sort-Object PSChildName -Descending)) {
                $install = Get-Item ($version.PSPath + '\InstallPath') -ErrorAction SilentlyContinue
                if ($install) {
                    $path = $install.GetValue('ExecutablePath')
                    if (-not $path) { $path = Join-Path $install.GetValue('') 'python.exe' }
                    $candidates += [pscustomobject]@{ File = $path; Prefix = @() }
                }
            }
        }
    }
    foreach ($name in @('py.exe', 'python.exe', 'python3.exe')) {
        $command = Get-Command $name -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($command -and $command.Source -notmatch '\\Microsoft\\WindowsApps\\python') {
            $prefix = @()
            if ($name -eq 'py.exe') { $prefix = @('-3') }
            $candidates += [pscustomobject]@{ File = $command.Source; Prefix = $prefix }
        }
    }
    foreach ($candidate in $candidates) {
        try {
            $probe = Invoke-Native $candidate.File ($candidate.Prefix + @('-B', '-c', 'import sys, tkinter; assert sys.version_info >= (3, 10); print(sys.executable)')) 15
            if ($probe.Code -eq 0 -and $probe.Out.Trim()) { return $probe.Out.Trim() }
        } catch { } # Continue to another installed interpreter.
    }
    return $null
}

function Find-Compiler([string]$Python) {
    $result = Invoke-Native $Python @('-B', '-c', 'import server; print(server.compiler())') 15
    if ($result.Code -eq 0) { return $result.Out.Trim() }
    if ($env:DIC_CC) {
        throw "DIC_CC ist gesetzt, funktioniert aber nicht. Pfad pruefen oder die eigene Vorgabe entfernen.`n$($result.Err)"
    }
    return $null
}

function Test-Compiler([string]$Compiler) {
    $temporary = Join-Path ([System.IO.Path]::GetTempPath()) ('dic compiler check ' + [guid]::NewGuid().ToString('N'))
    [void](New-Item -ItemType Directory -Path $temporary)
    try {
        $source = Join-Path $temporary 'check.c'
        $binary = Join-Path $temporary 'check.exe'
        $program = '#include <stdint.h>', '#include <stdio.h>', 'int main(void) { uint8_t n = 42; if(n != 42) return 1; puts("DIC compiler OK"); return 0; }'
        [System.IO.File]::WriteAllLines($source, $program, [System.Text.Encoding]::ASCII)
        $environment = @{ PATH = (Split-Path $Compiler) + [System.IO.Path]::PathSeparator + $env:PATH }
        $build = Invoke-Native $Compiler @('-std=gnu11', $source, '-o', $binary) 30 $temporary $environment
        if ($build.Code -ne 0) { throw "Compiler kann kein C-Programm erstellen:`n$($build.Out)`n$($build.Err)" }
        $run = Invoke-Native $binary @() 10 $temporary $environment
        if ($run.Code -ne 0 -or $run.Out.Trim() -ne 'DIC compiler OK') { throw "C-Programm laesst sich nicht ausfuehren (Code $($run.Code)).`n$($run.Err)" }
    } finally { Remove-Item -LiteralPath $temporary -Recurse -Force -ErrorAction SilentlyContinue }
}

function Get-MsysRoot {
    if ($env:MSYS2_ROOT) { return $env:MSYS2_ROOT }
    return 'C:\msys64'
}

function Install-WingetPackage([string]$Winget, [string]$Id, [string[]]$Extra = @()) {
    Write-Host "Installiere $Id. Das kann einige Minuten dauern ..."
    $result = Invoke-Native $Winget (@('install', '--id', $Id, '--exact', '--source', 'winget', '--scope', 'user', '--architecture', 'x64', '--silent', '--accept-source-agreements', '--accept-package-agreements', '--disable-interactivity') + $Extra) 1200
    Write-Host $result.Out
    if ($result.Err) { Write-Host $result.Err }
    return $result.Code
}

function Install-Compiler([string]$Winget) {
    $root = Get-MsysRoot
    # Only a local drive path without shell syntax: the root is passed as an
    # installer argument, never inserted into the bash command below.
    if ($root -notmatch '^[A-Za-z]:[\\/][A-Za-z0-9_\\/-]+$') {
        throw 'MSYS2_ROOT muss ein lokaler Laufwerkspfad ohne Leerzeichen sein, z. B. C:\msys64.'
    }
    $bash = Join-Path $root 'usr\bin\bash.exe'
    if (-not (Test-Path $bash -PathType Leaf)) {
        if (Test-Path $root) { throw "In $root liegt keine verwendbare MSYS2-Installation. Ordner pruefen; vorhandene Dateien werden nicht ueberschrieben." }
        $code = Install-WingetPackage $Winget 'MSYS2.MSYS2' @('--location', $root)
        if (-not (Test-Path $bash -PathType Leaf)) { throw "MSYS2-Installation fehlgeschlagen (Code $code). Details stehen oben. Siehe auch README." }
    }
    $environment = @{ MSYSTEM = 'UCRT64'; CHERE_INVOKING = 'yes' }
    $initialize = Invoke-Native $bash @('-lc', 'true') 120 $root $environment
    if ($initialize.Code -ne 0) { throw "MSYS2 konnte nicht initialisiert werden.`n$($initialize.Err)" }
    # A core update can terminate its own shell. Always start a fresh shell for
    # the full update; only accept termination of pass 1 if the next pass works.
    Write-Host 'Aktualisiere MSYS2 (zwei Durchlaeufe) ...'
    $core = Invoke-Native $bash @('-lc', 'pacman --noconfirm -Syu') 1200 $root $environment
    Write-Host $core.Out
    if ($core.Err) { Write-Host $core.Err }
    $full = Invoke-Native $bash @('-lc', 'pacman --noconfirm -Syu') 1200 $root $environment
    Write-Host $full.Out
    if ($full.Code -ne 0) { throw "MSYS2-Update fehlgeschlagen.`n$($full.Err)" }
    Write-Host 'Installiere den UCRT64 C-Compiler ...'
    $gcc = Invoke-Native $bash @('-lc', 'pacman --noconfirm -S --needed mingw-w64-ucrt-x86_64-gcc') 1200 $root $environment
    Write-Host $gcc.Out
    if ($gcc.Code -ne 0) { throw "Compilerinstallation fehlgeschlagen.`n$($gcc.Err)" }
}

function Invoke-Setup {
    $python = Find-Python
    $compiler = $null
    if ($python) { $compiler = Find-Compiler $python }
    Write-Host 'DIC Visualisierung - Windows einrichten'
    if ($python) { Write-Host "Python vorhanden: $python" } else { Write-Host 'Python 3.10+ mit tkinter fehlt. Installiert wird Python 3.13.' }
    if ($compiler) { Write-Host "Compiler vorhanden: $compiler" } else { Write-Host 'Compiler wird nach der Python-Pruefung eingerichtet, falls er fehlt.' }
    if (-not $python -or -not $compiler) {
        $winget = Get-Command winget.exe -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
        if (-not $winget) {
            throw 'Windows App-Installer (winget) fehlt. Im Microsoft Store die Microsoft-App "App-Installer" installieren/aktualisieren und diese Datei erneut starten. Anleitung: https://learn.microsoft.com/windows/package-manager/winget/'
        }
        Write-Host 'Die Einrichtung laedt fehlende Programme ueber Microsoft winget aus offiziellen Anbieter-Downloads.'
        Write-Host 'MSYS2 wird bei fehlendem Compiler ggf. aktualisiert. Vorher alle MSYS2/UCRT64-Fenster schliessen.'
        Write-Host 'Paket- und Quellenvereinbarungen werden dabei angenommen. Internet wird benoetigt.'
        if ((Read-Host 'Jetzt einrichten? [J/N]').Trim() -notmatch '^(j|ja|y|yes)$') {
            Write-Host 'Abgebrochen. Es wurde nichts installiert.'
            return 2
        }
        if (-not $python) {
            $code = Install-WingetPackage $winget.Source 'Python.Python.3.13'
            $python = Find-Python
            if (-not $python) { throw "Python-Installation nicht verwendbar (Code $code). Details stehen oben. Python 3.10+ inklusive tkinter ist erforderlich; siehe README." }
        }
        # Reuse the application's compiler selection, including DIC_CC/MSYS2_ROOT.
        $compiler = Find-Compiler $python
        if (-not $compiler) {
            Install-Compiler $winget.Source
            $compiler = Find-Compiler $python
            if (-not $compiler) { throw 'Der installierte Compiler wurde nicht erkannt. MSYS2_ROOT/DIC_CC und die README pruefen.' }
        }
    }
    Write-Host 'Pruefe C-Kompilierung und Ausfuehrung ...'
    Test-Compiler $compiler
    Write-Host "Erfolgreich. Python: $python"
    Write-Host "Compiler: $compiler"
    Write-Host 'Jetzt Start_Windows.bat doppelklicken und im Browser den Firmware-Ordner auswaehlen.'
    return 0
}

$script:ProjectRoot = Split-Path -Parent $PSScriptRoot
if ($MyInvocation.InvocationName -ne '.') {
    $ErrorActionPreference = 'Stop'
    try {
        if ($env:OS -ne 'Windows_NT') { throw 'Dieser Starter ist nur fuer Windows. Unter macOS Start_macOS.command verwenden.' }
        if (-not [Environment]::Is64BitOperatingSystem) { throw 'Die automatische Einrichtung benoetigt 64-Bit-Windows.' }
        if ($env:PROCESSOR_ARCHITECTURE -eq 'ARM64' -or $env:PROCESSOR_ARCHITEW6432 -eq 'ARM64') {
            Write-Host 'Hinweis: Windows ARM ist nicht validiert. Die Einrichtung verwendet x64-Pakete und benoetigt x64-Emulation.'
        }
        if ($Setup) { exit (Invoke-Setup) }
        if (-not $Launch) { throw 'Bitte Einrichtung_Windows.bat oder Start_Windows.bat verwenden.' }
        $python = Find-Python
        if (-not $python) { throw 'Python 3.10+ mit tkinter fehlt. Zuerst Einrichtung_Windows.bat doppelklicken.' }
        if (-not (Find-Compiler $python)) { throw 'C-Compiler fehlt. Zuerst Einrichtung_Windows.bat doppelklicken.' }
        Set-Location -LiteralPath $script:ProjectRoot
        & $python -B (Join-Path $script:ProjectRoot 'start.py')
        exit $LASTEXITCODE
    } catch {
        Write-Host "`nEinrichtung/Start fehlgeschlagen: $($_.Exception.Message)" -ForegroundColor Red
        exit 1
    }
}
