@echo off
call conda activate bci-ssvep
cd /d C:\Users\23842\Desktop\bci\online
python online_fbcca.py --window 1.5 --freqs 10,12,15,20 --chs 0,1,2,3 --vote 3
pause
