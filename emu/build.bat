@echo off
rem Builds pacemu.dll with clang-cl (LLVM) if installed, else MSVC cl; clang-cl's build runs ~25% faster.
setlocal
for /f "usebackq tokens=*" %%i in (`"%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do set VS=%%i
call "%VS%\VC\Auxiliary\Build\vcvars64.bat" >nul || exit /b 1
cd /d "%~dp0"
set CC=cl /W3
if exist "%ProgramFiles%\LLVM\bin\clang-cl.exe" set CC="%ProgramFiles%\LLVM\bin\clang-cl.exe" -Wno-everything
echo %CC%
%CC% /nologo /O2 /LD /D_CRT_SECURE_NO_WARNINGS pacemu.c /Fe:pacemu.dll /link /NOLOGO || exit /b 1
del /q *.obj pacemu.exp pacemu.lib 2>nul
