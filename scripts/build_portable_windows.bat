@echo off
setlocal

python -m venv .venv
call .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r indexador_documentos\requirements.txt
pip install pyinstaller

pyinstaller --noconfirm --clean AppPortable.spec

if not exist dist\AppPortable\data\input mkdir dist\AppPortable\data\input
if not exist dist\AppPortable\data\output mkdir dist\AppPortable\data\output
if not exist dist\AppPortable\data\app_state mkdir dist\AppPortable\data\app_state
if not exist dist\AppPortable\data\temp mkdir dist\AppPortable\data\temp

echo Build completado en dist\AppPortable\AppPortable.exe
endlocal
