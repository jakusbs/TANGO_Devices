#!/bin/sh

# insert shebang
sed '1s;^;#!/usr/bin/env python3\n;' PyKeithleyPulse.py > PyKeithleyPulse
chmod +x PyKeithleyPulse
mv PyKeithleyPulse /usr/local/tango_servers
