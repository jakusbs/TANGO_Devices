#!/bin/sh

# insert shebang
sed '1s;^;#!/usr/bin/env python3\n;' PyKeithley.py > PyKeithley
chmod +x PyKeithley
mv PyKeithley /usr/local/tango_servers
