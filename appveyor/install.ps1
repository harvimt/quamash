# Adapted from Sample script to install Python and pip under Windows
# Authors: Olivier Grisel and Kyle Kastner
# License: CC0 1.0 Universal: http://creativecommons.org/publicdomain/zero/1.0/
# Adapted by Mark Harviston <mark.harviston@gmail.com>

$BASE_URL = "https://www.python.org/ftp/python/"
$GET_PIP_URL = "https://bootstrap.pypa.io/get-pip.py"
$GET_PIP_PATH = "C:\get-pip.py"

function InstallPip ($python_home) {
    $pip_path = $python_home + "\Scripts\pip.exe"
    $python_path = $python_home + "\python.exe"
    if (-not(Test-Path $pip_path)) {
        Write-Host "Installing pip..."
        $webclient = New-Object System.Net.WebClient
        $webclient.DownloadFile($GET_PIP_URL, $GET_PIP_PATH)
        Write-Host "Executing:" $python_path $GET_PIP_PATH
        Start-Process -FilePath "$python_path" -ArgumentList "$GET_PIP_PATH" -Wait -Passthru
    } else {
        Write-Host "pip already installed."
    }
}

function InstallPackage ($python_home, $pkg) {
    $pip_path = $python_home + "\Scripts\pip.exe"
    & $pip_path install $pkg
}

function main () {
    InstallPip $env:PYTHON
    InstallPackage $env:PYTHON wheel
    InstallPackage $env:PYTHON pytest
    if($env:PYTHON_VERSION -match "^3.3"){
        InstallPackage $env:PYTHON asyncio
    }
    if($env:QTIMPL -eq "PySide"){
        InstallPackage $env:Python PySide
    }
}

main
