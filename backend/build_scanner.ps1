# build_scanner.ps1
# This script builds the ai-security-scanner-sandbox image required for Feature 3

Write-Host "Building Ephemeral Scanner Docker Image..." -ForegroundColor Cyan

docker build -t ai-security-scanner-sandbox -f Dockerfile.scanner .

if ($LASTEXITCODE -eq 0) {
    Write-Host "Build completed successfully!" -ForegroundColor Green
    Write-Host "The 'ai-security-scanner-sandbox' image is now ready for use by the backend orchestrator." -ForegroundColor Green
} else {
    Write-Host "Docker build failed." -ForegroundColor Red
}
