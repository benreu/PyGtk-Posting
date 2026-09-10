#!/bin/bash

config_dir=$HOME"/.config/posting/"
if [ ! -d $config_dir ]; then
	mkdir $config_dir
fi
log_dir=$HOME"/.config/posting/logs"
if [ ! -d $log_dir ]; then
	mkdir $log_dir
fi
RELATIVEDIR=`echo $0|sed s/run.sh//g`
cd $RELATIVEDIR

# The label designer lives in the LinuxZPL submodule, which a plain clone
# leaves empty. The .gitmodules test keeps this a no-op outside a checkout.
if [ -f .gitmodules ] && [ ! -d src/linuxzpl/zplcore ]; then
	echo "fetching the LinuxZPL submodule ..."
	git submodule update --init src/linuxzpl
fi

LOG_FILE=$log_dir/`echo $0|date +%Y-%m-%d:%H:%M:%S`
echo "log file is" $LOG_FILE
chmod +x ./src/main.py &> "$LOG_FILE"
python3 -u ./src/main.py $LOG_FILE |& tee $LOG_FILE
