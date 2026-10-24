@echo off
rem Builds pacemu.dll. With clang-cl (LLVM) installed: a profile-guided build (instrumented build,
rem pgo_train.py, rebuild with the profile), ~40% faster than MSVC. Else MSVC cl.
setlocal
for /f "usebackq tokens=*" %%i in (`"%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do set VS=%%i
call "%VS%\VC\Auxiliary\Build\vcvars64.bat" >nul || exit /b 1
cd /d "%~dp0"
set FLAGS=/nologo /O2 /LD /D_CRT_SECURE_NO_WARNINGS
set LLVM=%ProgramFiles%\LLVM
if not exist "%LLVM%\bin\clang-cl.exe" (
  cl %FLAGS% /W3 pacemu.c /Fe:pacemu.dll /link /NOLOGO || exit /b 1
  goto done
)
set CC="%LLVM%\bin\clang-cl.exe" %FLAGS% -Wno-everything
for /f "delims=" %%r in ('dir /b /s "%LLVM%\lib\clang\clang_rt.profile-x86_64.lib"') do set RT=%%r
set PGO=%TEMP%\pacemu-pgo
if exist "%PGO%" rd /s /q "%PGO%"
mkdir "%PGO%"
%CC% -fprofile-instr-generate="%PGO%\pm-%%p.profraw" pacemu.c /Fe:"%PGO%\gen.dll" /Fo:"%PGO%\\" /link /NOLOGO "%RT%" || exit /b 1
set PACEMU_DLL=%PGO%\gen.dll
python pgo_train.py || exit /b 1
set PACEMU_DLL=
"%LLVM%\bin\llvm-profdata.exe" merge -o "%PGO%\pm.profdata" "%PGO%\pm-*.profraw" || exit /b 1
%CC% -fprofile-instr-use="%PGO%\pm.profdata" pacemu.c /Fe:pacemu.dll /link /NOLOGO || exit /b 1
rd /s /q "%PGO%"
:done
del /q *.obj pacemu.exp pacemu.lib 2>nul
