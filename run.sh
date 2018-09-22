#!/bin/bash

config_dir=$HOME"/.config/posting/"
if [ ! -d $config_dir ]; then
	mkdir $config_dir
	mkdir $config_dir"logs/"
fi
RELATIVEDIR=`echo $0|sed s/run.sh//g`
cd $RELATIVEDIR

LOG_FILE=$config_dir"logs/`echo $0|date +%Y-%m-%d:%H:%M:%S`"
echo "log file is" $LOG_FILE
chmod +x ./src/pygtk_posting.py &> "$LOG_FILE"
python3 -u ./src/pygtk_posting.py "$LOG_FILE" &>> "$LOG_FILE"
