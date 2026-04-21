#!/bin/sh 

# insert shebang
sed '1s;^;#!/usr/bin/env python3\n;' PyHysteresis.py > PyHysteresis
chmod +x PyHysteresis
mv PyHysteresis /usr/local/tango_servers
