#!/bin/sh 

# insert shebang
sed '1s;^;#!/usr/bin/env python3\n;' AdsBridge2.py > AdsBridge2
chmod +x AdsBridge2
mv AdsBridge2 /usr/local/tango_servers

