@echo off
setlocal

REM Build .NET desktop native app (WPF) - no Python packaging

dotnet restore AppPortable.sln
if errorlevel 1 exit /b 1

dotnet build AppPortable.sln -c Release
if errorlevel 1 exit /b 1

dotnet publish AppPortable.Desktop\AppPortable.Desktop.csproj -c Release -r win-x64 --self-contained true /p:PublishSingleFile=true
if errorlevel 1 exit /b 1

echo Build completado en AppPortable.Desktop\bin\Release\net8.0-windows\win-x64\publish\AppPortable.exe
endlocal
