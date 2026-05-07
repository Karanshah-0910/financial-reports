@echo off
:: ============================================================
:: run_reports.bat
:: Called by Windows Task Scheduler on the 1st of each month.
:: Activates the virtual environment and runs the report batch.
:: ============================================================

cd /d "C:\Users\karan\OneDrive\Desktop\Karan\financial-reports"

:: Activate virtual environment
call venv\Scripts\activate.bat

:: Run the batch — sends client reports automatically
python run_monthly_reports.py --send-clients >> logs\scheduler.log 2>&1

:: Deactivate when done
deactivate
