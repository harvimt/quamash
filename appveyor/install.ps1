# Adapted from Sample script to install Python and pip under Windows
# Authors: Olivier Grisel and Kyle Kastner
# License: CC0 1.0 Universal: http://creativecommons.org/publicdomain/zero/1.0/
# Adapted by Mark Harviston <mark.harviston@gmail.com>

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
	$PYTHON_MAJ_VERSION = $env:PYTHON_VERSION -replace '(\d+)\.(\d+)\.(\d+)', '$1.$2'
	& REG ADD "HKCU\Software\Python\PythonCore\${PYTHON_MAJ_VERSION}\InstallPath" /f /ve /t REG_SZ /d $env:PYTHON
	InstallPip $env:PYTHON
	InstallPackage $env:PYTHON wheel
	InstallPackage $env:PYTHON pytest
	InstallPackage $env:PYTHON pytest-timeout
	InstallPackage $env:PYTHON pytest-xdist
	if($PYTHON_MAJ_VERSION -eq '3.3'){
		InstallPackage $env:PYTHON asyncio
	}
	switch ($env:QTIMPL){
		"PySide" {
			InstallPackage $env:Python PySide
		}
		"PyQt4" {
			(new-object net.webclient).DownloadFile("http://sourceforge.net/projects/pyqt/files/PyQt4/PyQt-4.11.4/PyQt4-4.11.4-gpl-Py3.4-Qt4.8.7-x32.exe/download", "C:\install-PyQt4.exe")
			Start-Process -FilePath C:\install-PyQt4.exe -ArgumentList "/S" -Wait -Passthru
		}
		"PyQt5" {
			(new-object net.webclient).DownloadFile("http://sourceforge.net/projects/pyqt/files/PyQt5/PyQt-5.5.1/PyQt5-5.5.1-gpl-Py3.4-Qt5.5.1-x32.exe/download", "C:\install-PyQt5.exe")
			Start-Process -FilePath C:\install-PyQt5.exe -ArgumentList "/S" -Wait -Passthru
		}
	}
}

main
