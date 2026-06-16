param(
    [switch]$Restore
)

$RegistryPath = "HKLM:\SYSTEM\CurrentControlSet\Control\GraphicsDrivers"

# Check if running as administrator
if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "This script must be run as Administrator to modify registry settings."
    Write-Host "If it fails, please run Pinokio as Administrator."
}

if ($Restore) {
    Write-Host "Restoring default TDR settings..."
    Remove-ItemProperty -Path $RegistryPath -Name "TdrDelay" -ErrorAction SilentlyContinue
    Remove-ItemProperty -Path $RegistryPath -Name "TdrDdiDelay" -ErrorAction SilentlyContinue
    Remove-ItemProperty -Path $RegistryPath -Name "TdrLevel" -ErrorAction SilentlyContinue
    Write-Host "Defaults restored. Please restart your computer for changes to take effect."
} else {
    Write-Host "Increasing Windows GPU Timeout (TDR)..."
    
    # Check if the registry path exists
    if (-not (Test-Path $RegistryPath)) {
        New-Item -Path $RegistryPath -Force | Out-Null
    }

    # Set TdrDelay to 60 seconds
    New-ItemProperty -Path $RegistryPath -Name "TdrDelay" -PropertyType DWORD -Value 60 -Force | Out-Null
    
    # Set TdrDdiDelay to 60 seconds
    New-ItemProperty -Path $RegistryPath -Name "TdrDdiDelay" -PropertyType DWORD -Value 60 -Force | Out-Null

    # Set TdrLevel to 3 (Recover on timeout)
    New-ItemProperty -Path $RegistryPath -Name "TdrLevel" -PropertyType DWORD -Value 3 -Force | Out-Null

    Write-Host "TDR Timeout increased to 60 seconds."
    Write-Host "IMPORTANT: You MUST RESTART your computer for these changes to take effect."
}
