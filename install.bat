@echo off
echo Installing Dirigent...

echo Creating Python virtual environment...
python -m venv venv

echo Activating virtual environment...
call venv\Scripts\activate.bat

echo Installing backend dependencies...
pip install -r backend\requirements.txt

echo Installing frontend dependencies...
cd frontend
call npm install
cd ..

echo.
echo Installation complete!
echo.
echo To run the backend:
echo   run_backend.bat
echo.
echo To run the frontend:
echo   run_frontend.bat
