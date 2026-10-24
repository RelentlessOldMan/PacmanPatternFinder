@echo off
rem Builds pacemu.dll with MSVC (Visual Studio 2022 C++ tools).
setlocal
for /f "usebackq tokens=*" %%i in (`"%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do set VS=%%i
call "%VS%\VC\Auxiliary\Build\vcvars64.bat" >nul || exit /b 1
cd /d "%~dp0"
cl /nologo /O2 /LD /W3 /D_CRT_SECURE_NO_WARNINGS pacemu.c z80.c /Fe:pacemu.dll /link /NOLOGO || exit /b 1
del /q *.obj pacemu.exp pacemu.lib 2>nul
