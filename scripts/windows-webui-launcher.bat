@echo off
REM Z-Image Studio Web UI Launcher
REM Starts the server and opens the browser

setlocal EnableDelayedExpansion

set SERVER_URL=http://localhost:8000
set TIMEOUT=30
set POLL_INTERVAL_MS=500

echo Starting Z-Image Studio server...

REM Start server in hidden window using PowerShell
powershell -WindowStyle Hidden -Command ^
    "$p = Start-Process -FilePath '%~dp0\zimg.exe' -ArgumentList 'serve --host 0.0.0.0 --port 8000' -PassThru -NoNewWindow; ^
     Start-Sleep -Seconds 2; ^
     $client = New-Object System.Net.WebClient; ^
     $timeout = [DateTime]::Now.AddSeconds(%TIMEOUT%); ^
     while ([DateTime]::Now -lt $timeout) { ^
         try { $response = $client.DownloadString('%SERVER_URL%'); break; } ^
         catch { Start-Sleep -Milliseconds %POLL_INTERVAL_MS%; } ^
     }; ^
     Start-Process '%SERVER_URL%'"

if %errorlevel% equ 0 (
    echo Server started! Opening %SERVER_URL% in your browser...
    echo Press Ctrl+C to stop the server.
) else (
    echo ERROR: Failed to start server.
    exit /b 1
)

endlocal
pause
