# Build script for Ray VLLM Service
# Usage: .\build.ps1 [dev|prod]

param(
    [string]$Mode = "dev"
)

$ErrorActionPreference = "Stop"

Write-Host "🚀 Building Ray VLLM Service..." -ForegroundColor Cyan

if ($Mode -eq "dev") {
    Write-Host "📦 Mode: Development (faster build, larger image)" -ForegroundColor Yellow
    $dockerfile = "Dockerfile.dev"
    $tag = "ray-vllm-service:dev"
} else {
    Write-Host "📦 Mode: Production (optimized, smaller image)" -ForegroundColor Green
    $dockerfile = "Dockerfile"
    $tag = "ray-vllm-service:v2.49.0"
}

Write-Host "🔨 Building image: $tag" -ForegroundColor Cyan
Write-Host "📄 Using: $dockerfile" -ForegroundColor Cyan

# Build with BuildKit for better caching
$env:DOCKER_BUILDKIT = 1

$buildCmd = "docker build -f $dockerfile -t $tag ."

Write-Host "⏳ Starting build (this may take 10-15 minutes on first run)..." -ForegroundColor Yellow
Write-Host ""

try {
    Invoke-Expression $buildCmd
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "✅ Build successful!" -ForegroundColor Green
        Write-Host "📦 Image: $tag" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "🚀 To run the container:" -ForegroundColor Yellow
        Write-Host "   docker run --gpus all -p 8000:8000 -p 8265:8265 $tag" -ForegroundColor White
        Write-Host ""
        
        # Show image size
        $size = docker images $tag --format "{{.Size}}"
        Write-Host "💾 Image size: $size" -ForegroundColor Cyan
    } else {
        Write-Host ""
        Write-Host "❌ Build failed!" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host ""
    Write-Host "❌ Build error: $_" -ForegroundColor Red
    exit 1
}
