@echo off
setlocal
REM Cosim_bridge launcher: matched TraCI DLLs first, then optional SUMO_HOME\bin for sumo.exe
set "BRIDGE_DIR=%~dp0"
set "PATH=%BRIDGE_DIR%;%PATH%"
if defined SUMO_HOME (
  if exist "%SUMO_HOME%\bin" set "PATH=%PATH%;%SUMO_HOME%\bin"
)
"%BRIDGE_DIR%Cosim_bridge.exe" %*
exit /b %ERRORLEVEL%
