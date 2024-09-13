@echo off
setlocal enabledelayedexpansion

REM Navigate to the SDK directory where you have your top level .py files
cd /d path_to_your_sdk
REM cd /d C:\SnowfallTravel\src\python_sdk\junction

REM Generate the SDK documentation using Sphinx
REM sphinx-build -b <format to convert into - html> <path of the source dir containing conf.py> <path of where the html files should be created i.e docs\source docs\build\html>
sphinx-build -b html ..\docs\source ..\docs\build\html

REM Check if the Sphinx build was successful
if %errorlevel% neq 0 (
    echo Sphinx build failed. Exiting...
    exit /b %errorlevel%
)

REM Sync the documentation with Docusaurus static directory
REM xcopy <options> <path where documentation is generated> <path to copy the documentation in monorepo docs folder>
xcopy /s /e /y /q /i ..\docs\build\html path_to_docusaurus\static\sdk-docs

REM Verify if the copy was successful
if %errorlevel% neq 0 (
    echo File copy failed. Exiting...
    exit /b %errorlevel%
)

echo Documentation successfully updated and synced with Docusaurus.

endlocal
pause