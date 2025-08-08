@echo off
call conda activate bci-ssvep
cd /d C:\Users\23842\Desktop\bci\online
python online_cca.py --window 1.0 --freqs 10,12,15,20 --notch 50
pause


