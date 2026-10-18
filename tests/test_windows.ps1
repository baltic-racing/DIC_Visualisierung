param([string]$PythonForTest)
$ErrorActionPreference = 'Stop'
. (Join-Path (Split-Path $PSScriptRoot) 'windows.ps1')
if (-not (Get-PSDrive C -ErrorAction SilentlyContinue)) {
    # Only a PowerShell provider mapping on non-Windows test hosts; no disk writes.
    [void](New-PSDrive -Name C -PSProvider FileSystem -Root ([System.IO.Path]::GetTempPath()) -Scope Script)
}
$script:Count = 0
function Assert($Condition, [string]$Message) { if (-not $Condition) { throw $Message } }
function Assert-Throws([scriptblock]$Action, [string]$Pattern) {
    try { & $Action } catch {
        Assert ($_.Exception.Message -match $Pattern) "Unexpected error: $($_.Exception.Message)"
        return
    }
    throw "Expected an error matching $Pattern"
}
function Check([string]$Name, [scriptblock]$Action) {
    & $Action
    $script:Count++
    Write-Host "PASS $Name"
}

Check 'Native argument quoting' {
    Assert ((ConvertTo-NativeArgument '') -ceq '""') 'Empty argument lost'
    Assert ((ConvertTo-NativeArgument 'C:\folder with spaces\') -ceq '"C:\folder with spaces\\"') 'Trailing slash quoting failed'
    Assert ((ConvertTo-NativeArgument 'say "hello"') -ceq '"say \"hello\""') 'Embedded quote failed'
}

Check 'Python probe rejects incompatible interpreters and uses next candidate' {
    $script:Probes = 0
    function Test-Path { return $false }
    function Get-Command($Name) {
        if ($Name -in @('py.exe', 'python.exe')) { return [pscustomobject]@{ Source = $Name } }
    }
    function Invoke-Native($File, $Arguments) {
        $script:Probes++
        Assert ($Arguments -contains '-c') 'Missing Python probe'
        if ($File -eq 'py.exe') { return [pscustomobject]@{ Code = 1; Out = ''; Err = 'tkinter unavailable' } }
        return [pscustomobject]@{ Code = 0; Out = 'C:\Python\python.exe'; Err = '' }
    }
    Assert ((Find-Python) -eq 'C:\Python\python.exe') 'Python fallback failed'
    Assert ($script:Probes -eq 2) 'Wrong number of interpreter probes'
}

Check 'Installed components require no network or confirmation' {
    $script:CompilerChecked = $false
    function Find-Python { 'python' }
    function Find-Compiler { 'gcc' }
    function Test-Compiler { $script:CompilerChecked = $true }
    function Get-Command { throw 'Unexpected network/setup prerequisite check' }
    function Read-Host { throw 'Unexpected confirmation' }
    Assert ((Invoke-Setup) -eq 0) 'Setup did not succeed'
    Assert $script:CompilerChecked 'Compiler was not tested'
}

Check 'Cancellation installs nothing' {
    function Find-Python { $null }
    function Get-Command { [pscustomobject]@{ Source = 'winget' } }
    function Read-Host { 'N' }
    function Install-WingetPackage { throw 'Install called after cancellation' }
    function Install-Compiler { throw 'Compiler install called after cancellation' }
    Assert ((Invoke-Setup) -eq 2) 'Cancellation exit code lost'
}

Check 'Missing winget has an actionable message' {
    function Find-Python { $null }
    function Get-Command { $null }
    Assert-Throws { Invoke-Setup } 'App-Installer'
}

Check 'Only missing Python is installed, compiler reused after recheck' {
    $script:PythonInstalled = $false
    function Find-Python { if ($script:PythonInstalled) { 'python' } }
    function Find-Compiler { 'gcc' }
    function Get-Command { [pscustomobject]@{ Source = 'winget' } }
    function Read-Host { 'J' }
    function Install-WingetPackage($Winget, $Id) {
        Assert ($Id -eq 'Python.Python.3.13') 'Unexpected package'
        $script:PythonInstalled = $true
        return 0
    }
    function Install-Compiler { throw 'Existing compiler should be reused' }
    function Test-Compiler { }
    Assert ((Invoke-Setup) -eq 0) 'Setup failed'
}

Check 'Failed Python installation is not reported as success' {
    function Find-Python { $null }
    function Get-Command { [pscustomobject]@{ Source = 'winget' } }
    function Read-Host { 'J' }
    function Install-WingetPackage { 123 }
    function Test-Compiler { throw 'Should not reach final check' }
    Assert-Throws { Invoke-Setup } 'Code 123'
}

Check 'Compiler installation happens only if missing' {
    $script:CompilerInstalled = $false
    function Find-Python { 'python' }
    function Find-Compiler { if ($script:CompilerInstalled) { 'gcc' } }
    function Get-Command { [pscustomobject]@{ Source = 'winget' } }
    function Read-Host { 'ja' }
    function Install-WingetPackage { throw 'Python should be reused' }
    function Install-Compiler { $script:CompilerInstalled = $true }
    function Test-Compiler { }
    Assert ((Invoke-Setup) -eq 0) 'Setup failed'
    Assert $script:CompilerInstalled 'Compiler not installed'
}

Check 'MSYS2 update restarts the shell after a terminating core update' {
    $script:Commands = @()
    function Get-MsysRoot { 'C:\msys64' }
    function Test-Path { $true }
    function Invoke-Native($File, $Arguments) {
        $script:Commands += $Arguments[-1]
        $code = 0
        if ($script:Commands.Count -eq 2) { $code = 137 }
        [pscustomobject]@{ Code = $code; Out = ''; Err = '' }
    }
    Install-Compiler 'winget'
    Assert ($script:Commands.Count -eq 4) 'Expected init, two updates, gcc install'
    Assert ($script:Commands[1] -eq $script:Commands[2]) 'Full update was not retried in a fresh shell'
    Assert ($script:Commands[-1] -match '--needed mingw-w64-ucrt-x86_64-gcc') 'Wrong compiler package'
}

Check 'Failed full MSYS2 update stops before compiler installation' {
    $script:Commands = 0
    function Get-MsysRoot { 'C:\msys64' }
    function Test-Path { $true }
    # Initialization must work before the update failure can be tested.
    function Invoke-Native {
        $script:Commands++
        $code = 1
        if ($script:Commands -eq 1) { $code = 0 }
        [pscustomobject]@{ Code = $code; Out = ''; Err = 'network failure' }
    }
    Assert-Throws { Install-Compiler 'winget' } 'Update fehlgeschlagen'
    Assert ($script:Commands -eq 3) 'Should not install GCC after failed update'
}

Check 'Failed MSYS2 installation is detected' {
    function Get-MsysRoot { 'C:\msys64' }
    function Test-Path { $false }
    function Install-WingetPackage { 123 }
    Assert-Throws { Install-Compiler 'winget' } 'Code 123'
}

Check 'Installer arguments use exact package and source, with verification enabled' {
    function Invoke-Native($File, $Arguments) {
        Assert ($Arguments -contains '--exact') 'Ambiguous package selection'
        Assert ($Arguments -contains '--source') 'Package source missing'
        Assert ($Arguments -contains 'winget') 'Wrong package source'
        Assert ($Arguments -notcontains '--ignore-security-hash') 'Hash checks disabled'
        [pscustomobject]@{ Code = 0; Out = ''; Err = '' }
    }
    Assert ((Install-WingetPackage 'winget' 'MSYS2.MSYS2') -eq 0) 'Exit code lost'
}

Check 'Invalid explicit compiler setting is not overwritten' {
    $previous = $env:DIC_CC
    try {
        $env:DIC_CC = 'invalid-compiler'
        function Invoke-Native { [pscustomobject]@{ Code = 1; Out = ''; Err = 'invalid compiler' } }
        Assert-Throws { Find-Compiler 'python' } 'DIC_CC'
    } finally { $env:DIC_CC = $previous }
}

Check 'Failed C build is reported' {
    function Invoke-Native { [pscustomobject]@{ Code = 1; Out = ''; Err = 'linker failure' } }
    Assert-Throws { Test-Compiler 'gcc' } 'linker failure'
}

Check 'Missing runtime DLL or failing C program is reported' {
    $script:Runs = 0
    function Invoke-Native {
        $script:Runs++
        $code = 0
        if ($script:Runs -eq 2) { $code = 1 }
        [pscustomobject]@{ Code = $code; Out = ''; Err = 'runtime failure' }
    }
    Assert-Throws { Test-Compiler 'gcc' } 'runtime failure'
}

if (-not $PythonForTest) { $PythonForTest = Find-Python }
if ($PythonForTest) {
    Check 'Native process preserves argument boundaries and special characters' {
        $expected = @('', 'space value', 'say "hello"', 'C:\a b\', 'literal $(test); & %PATH%')
        $result = Invoke-Native $PythonForTest (@('-c', 'import json, sys; print(json.dumps(sys.argv[1:]))') + $expected)
        Assert ($result.Code -eq 0) $result.Err
        $actual = @($result.Out | ConvertFrom-Json)
        Assert (($actual | ConvertTo-Json -Compress) -ceq ($expected | ConvertTo-Json -Compress)) 'Arguments changed'
    }
    Check 'Native process returns failure output' {
        $result = Invoke-Native $PythonForTest @('-c', 'import sys; print("failure", file=sys.stderr); sys.exit(7)')
        Assert ($result.Code -eq 7 -and $result.Err -match 'failure') 'Child failure lost'
    }
    Check 'Native process timeout' {
        Assert-Throws { Invoke-Native $PythonForTest @('-c', 'import time; time.sleep(10)') 1 } 'Zeitlimit'
    }
} else { Write-Host 'SKIP native process tests: no Python installed' }

$cc = Get-Command clang, gcc -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
if ($env:OS -eq 'Windows_NT' -and $PythonForTest) {
    $path = Find-Compiler $PythonForTest
    if ($path) { $cc = [pscustomobject]@{ Source = $path } }
}
if ($cc) {
    Check 'Actual C build and execution in a directory containing spaces' { Test-Compiler $cc.Source }
} else { Write-Host 'SKIP C build test: no compiler installed' }
Write-Host "$script:Count tests passed. No installations or downloads were performed."
