#!/bin/sh

# insert shebang
sed '1s;^;#!/usr/bin/env python3\n;' Magnet.py > Magnet
chmod +x Magnet
mv Magnet /usr/local/tango_servers
