@echo off
setlocal

python -m venv .venv
call .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r indexador_documentos\requirements.txt
pip install pyinstaller

pyinstaller --noconfirm AppPortable.spec

if not exist dist\AppPortable\input mkdir dist\AppPortable\input
if not exist dist\AppPortable\output mkdir dist\AppPortable\output
if not exist dist\AppPortable\index mkdir dist\AppPortable\index
if not exist dist\AppPortable\temp mkdir dist\AppPortable\temp

copy /Y assets\ui\ocr-pipeline-mockup.html dist\AppPortable\assets\ui\ocr-pipeline-mockup.html >nul

echo Build completado en dist\AppPortable
endlocal
