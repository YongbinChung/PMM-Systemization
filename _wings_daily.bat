@echo on
title WINGS Daily Auto-Fetch (07:00)
echo Starting WINGS daily download at %date% %time%...
"c:\Users\yongbin.chung.ext\Desktop\your-project\.venv\Scripts\python.exe" "c:\Users\yongbin.chung.ext\Desktop\your-project\_wings_daily.py"
echo.
echo Done. This window will close in 10 seconds.
timeout /t 10
