@echo off
REM Build the .exe using PyInstaller
pyinstaller --onefile --noconsole CrossPatch.py
pyinstaller --onefile --noconsole --icon=CrossP.png CrossPatch.py


REM After building, the .exe will be in the "dist" folder
echo Build complete! Your exe is in the dist folder.
pause
