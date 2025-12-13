#!/bin/bash
cd /home/ece4/PinyaSuri_ECE4
source pinyasuri_env/bin/activate
mavproxy.py --master=/dev/ttyAMA0 --baudrate=57600 \
  --out=udp:127.0.0.1:14551 \
  --daemon \
  --state-basedir=/tmp/mavproxy_pinyasuri