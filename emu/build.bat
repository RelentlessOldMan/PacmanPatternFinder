@echo off
rem Builds pacemu.dll: with clang-cl (LLVM) if installed (~40% faster than MSVC), else MSVC cl.
rem (A profile-guided clang build was slower once the opcode switch was inlined into the run loop.)
setlocal
for /f "usebackq tokens=*" %%i in (`"%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do set VS=%%i
call "%VS%\VC\Auxiliary\Build\vcvars64.bat" >nul || exit /b 1
cd /d "%~dp0"
set FLAGS=/nologo /O2 /LD /D_CRT_SECURE_NO_WARNINGS
set LLVM=%ProgramFiles%\LLVM
if exist "%LLVM%\bin\clang-cl.exe" (
  "%LLVM%\bin\clang-cl.exe" %FLAGS% -Wno-everything pacemu.c /Fe:pacemu.dll /link /NOLOGO || exit /b 1
) else (
  cl %FLAGS% /W3 pacemu.c /Fe:pacemu.dll /link /NOLOGO || exit /b 1
)
del /q *.obj pacemu.exp pacemu.lib 2>nul
