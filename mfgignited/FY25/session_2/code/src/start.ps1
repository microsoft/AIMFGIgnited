# set the parent of the script as the current location.
Set-Location $PSScriptRoot
$directory = Get-Location
$root = "$directory/.."
$backendPath = "$directory/backend"
$frontendPath = "$directory/frontend"

$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    $pythonCmd = Get-Command python3 -ErrorAction SilentlyContinue
    if (-not $pythonCmd) {
        Write-Error "Python is not installed or not found in PATH. Please install Python and try again."
        exit 1
    }
}

Write-Host 'Creating python virtual environment ".venv"'

$venvTarget = "$root/.venv"
Start-Process -FilePath ($pythonCmd).Source -ArgumentList "-m venv $venvTarget" -Wait -NoNewWindow

$venvPythonPath = "$root/.venv/scripts/python.exe"

Write-Host 'Installing dependencies from "requirements.txt" into virtual environment'
Start-Process -FilePath $venvPythonPath -ArgumentList "-m pip install -r $backendPath/requirements.txt" -Wait -NoNewWindow

# Load azd environment variables
Write-Host "Loading azd environment variables"
$azdEnv = azd env get-values --output json | ConvertFrom-Json
foreach ($key in $azdEnv.PSObject.Properties.Name) {
    [System.Environment]::SetEnvironmentVariable($key, $azdEnv.$key, [System.EnvironmentVariableTarget]::Process)
}

Write-Host ""
Write-Host "Restoring frontend npm packages"
Write-Host ""
Set-Location $frontendPath
npm install
if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to restore frontend npm packages"
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "Building frontend"
Write-Host ""
npm run build
if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to build frontend"
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "Starting app"
Write-Host ""
Set-Location $backendPath
Start-Process http://localhost:5000
Start-Process -FilePath $venvPythonPath -ArgumentList "app.py" -Wait -NoNewWindow
if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to start backend"
    exit $LASTEXITCODE
}

