# PM-System ???????????Windows??



# ?¡Â???powershell -ExecutionPolicy Bypass -File deploy\scripts\init_db.ps1



# ?????????????????/????? ?? ??? Alembic ?????? ?? §Õ??????????(????TR???/?????/????)



# ???????????? PostgreSQL 14+ ?? Python?????????????



param(



    [string]$PgHost = "127.0.0.1",



    [string]$PgPort = "5432",



    [string]$PgUser = "postgres",



    [string]$PgPassword = "",



    [string]$AppUser = "pm",



    [string]$AppPassword = "postgres",



    [string]$DbName = "pm_system",



    [string]$Psql = "",



    [string]$BackendDir = "",



    [string]$Python = ""    # ??§Á Python ¡¤????????¦Ä? Python ????????????/?????



)



$ErrorActionPreference = "Stop"



[Console]::OutputEncoding = [System.Text.Encoding]::UTF8







function Find-Psql {



    param([string]$Hint)



    if ($Hint -and (Test-Path $Hint)) { return $Hint }



    if (Get-Command psql -ErrorAction SilentlyContinue) { return (Get-Command psql).Source }



    # ???????¡¤????C:\Program Files\PostgreSQL\<version>\bin\psql.exe



    $root = "C:\Program Files\PostgreSQL"



    if (Test-Path $root) {



        $latest = Get-ChildItem $root -Directory | Sort-Object { [int]$_.Name } -Descending | Select-Object -First 1



        if ($latest) {



            $candidate = Join-Path $latest.FullName "bin\psql.exe"



            if (Test-Path $candidate) { return $candidate }



        }



    }



    throw "¦Ä??? psql?????? -Psql ??????? psql.exe ¡¤??????? PostgreSQL bin ???? PATH??"



}







$Psql = Find-Psql $Psql



if (-not $PgPassword) {



    $PgPassword = Read-Host "?????? PostgreSQL ???????($PgUser)????"



}



# ???????????????????? psql ????????????



$env:PGPASSWORD = $PgPassword



if (-not $BackendDir) {



    $BackendDir = Join-Path $PSScriptRoot "..\..\backend"



}



$BackendDir = [System.IO.Path]::GetFullPath($BackendDir)



if (-not (Test-Path (Join-Path $BackendDir "alembic.ini"))) {



    throw "????????????$BackendDir????? alembic.ini??"



}







Write-Host "==> psql:      $Psql" -ForegroundColor Cyan



Write-Host "==> ?????:  $BackendDir" -ForegroundColor Cyan



Write-Host "==> ????:    $DbName????? $AppUser??" -ForegroundColor Cyan







# 1. ???????????????????



Write-Host "==> ???/??????? $AppUser ..." -ForegroundColor Yellow



# ???psql ???????/???????????????? null???? Out-String ?? Trim??????"?? Null ????¡Â???"



$roleOut = (& $Psql -h $PgHost -p $PgPort -U $PgUser -d postgres -tAc "SELECT 1 FROM pg_roles WHERE rolname='$AppUser'" 2>$null) | Out-String



$roleExists = ("$roleOut".Trim() -eq "1")



if (-not $roleExists) {



    & $Psql -h $PgHost -p $PgPort -U $PgUser -d postgres -c "CREATE USER $AppUser WITH PASSWORD '$AppPassword'"



    Write-Host "   ???????? $AppUser" -ForegroundColor Green



} else {



    Write-Host "   ?????????????" -ForegroundColor DarkGray



}







Write-Host "==> ???/????????? $DbName ..." -ForegroundColor Yellow



$dbOut = (& $Psql -h $PgHost -p $PgPort -U $PgUser -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$DbName'" 2>$null) | Out-String



$dbExists = ("$dbOut".Trim() -eq "1")



if (-not $dbExists) {



    & $Psql -h $PgHost -p $PgPort -U $PgUser -d postgres -c "CREATE DATABASE $DbName OWNER $AppUser"



    Write-Host "   ?????????? $DbName" -ForegroundColor Green



} else {



    Write-Host "   ???????????????" -ForegroundColor DarkGray



}







# 2. §Õ??? .env ?? DATABASE_URL????????????I/?????



$envFile = Join-Path $BackendDir ".env"



if (-not (Test-Path $envFile)) {



    if (Test-Path (Join-Path $BackendDir ".env.example")) {



        Copy-Item (Join-Path $BackendDir ".env.example") $envFile



    }



}



if (Test-Path $envFile) {



    $content = Get-Content $envFile -Raw



    $url = "postgresql+psycopg2://$AppUser`:$AppPassword@$PgHost`:$PgPort/$DbName"



    if ($content -match "(?m)^DATABASE_URL=.*") {



        $content = $content -replace "(?m)^DATABASE_URL=.*", "DATABASE_URL=$url"



    } else {



        $content += "`nDATABASE_URL=$url`n"



    }



    Set-Content -Path $envFile -Value $content -Encoding UTF8



    Write-Host "==> ????? $envFile ?? DATABASE_URL" -ForegroundColor Green



}







# 3. Alembic ??????



Write-Host "==> ??? Alembic ??????????..." -ForegroundColor Yellow



Push-Location $BackendDir



try {



    $PyDir = $BackendDir.Replace('\', '/')



    if ($Python -and (Test-Path $Python)) {

        & $Python -m alembic upgrade head

    } elseif (Test-Path (Join-Path $BackendDir "venv\Scripts\alembic.exe")) {



        & (Join-Path $BackendDir "venv\Scripts\alembic.exe") upgrade head



    } elseif (Get-Command alembic -ErrorAction SilentlyContinue) {



        & alembic upgrade head



    } else {



        python -m alembic upgrade head



    }



    if ($LASTEXITCODE -ne 0) { throw "Alembic ??????" }



    Write-Host "   ??????" -ForegroundColor Green







    # 4. ??????????? psql ?????? PATH???? seed ????????? psql ??§µ?



    Write-Host "==> §Õ???????????????TR???/?????/?????..." -ForegroundColor Yellow



    $psqlDir = Split-Path $Psql



    if ($env:PATH -notlike "*$psqlDir*") {



        $env:PATH = "$psqlDir;$env:PATH"



    }



    if ($Python -and (Test-Path $Python)) {



        & $Python -c "import sys; sys.path.insert(0, r'$PyDir'); from app.seed import run; sys.exit(run())"



    } elseif (Get-Command python -ErrorAction SilentlyContinue) {



        & python -c "import sys; sys.path.insert(0, r'$PyDir'); from app.seed import run; sys.exit(run())"



    } else {



        & (Join-Path $BackendDir "venv\Scripts\python.exe") -c "import sys; sys.path.insert(0, r'$PyDir'); from app.seed import run; sys.exit(run())"



    }



    if ($LASTEXITCODE -ne 0) { throw "????????§Õ?????" }



    Write-Host "   ???????????" -ForegroundColor Green



} finally {



    Pop-Location



}







Write-Host ""



Write-Host "==========================================" -ForegroundColor Green



Write-Host "[OK] ?????????????$DbName"



Write-Host "   ??????: $AppUser / $AppPassword"



Write-Host "   ????????: admin / admin123????????????????"



Write-Host "==========================================" -ForegroundColor Green



