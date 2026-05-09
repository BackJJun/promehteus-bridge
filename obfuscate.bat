@echo off
chcp 65001 > nul
echo ========================================
echo PyArmor 난독화 스크립트 (Windows)
echo ========================================
echo.

REM PyArmor 설치 확인

echo 난독화 프로세스 시작...
python obfuscate_app.py

if %errorlevel% equ 0 (
    echo.
    echo [3/3] 완료!
    echo ✅ 난독화가 성공적으로 완료되었습니다.
    echo 📁 결과물 위치: obfuscation 폴더
    echo 🚀 실행: obfuscation\run_obfuscated.bat
) else (
    echo.
    echo ❌ 난독화 중 오류가 발생했습니다.
    echo 📋 obfuscation.log 파일을 확인해주세요.
)

echo.
pause
