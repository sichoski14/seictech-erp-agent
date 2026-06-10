@echo off
echo ========================================
echo INICIANDO SISTEMA DE ANALISE DE VAREJO
echo ========================================
echo.
call .\venv\Scripts\activate
echo.
echo 🔄 Iniciando servidor...
echo.
echo 🌐 Acesse: http://localhost:5000
echo.
echo ⚠️  Para parar: pressione Ctrl+C
echo ========================================
echo.
python sistema_completo.py
pause