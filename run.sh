#!/bin/bash


RELATIVEDIR=`echo $0|sed s/run.sh//g`
cd $RELATIVEDIR

if [ ! -d ~/.posting ];then
	mkdir ~/.posting
	cp db_settings ~/.posting
fi
LOG_FILE="logs/`echo $0|date +%Y-%m-%d:%H:%M:%S`"
echo "log file is" $LOG_FILE
chmod +x ./src/pygtk_posting.py &> "$LOG_FILE"
python3 -u ./src/pygtk_posting.py "$LOG_FILE" &>> "$LOG_FILE"
