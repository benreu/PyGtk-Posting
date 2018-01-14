#! /bin/bash

RELATIVEDIR=`echo $0|sed s/create_diff.sh//g`
cd $RELATIVEDIR

diff -u -r ./oldsrc ./src > posting.diff
