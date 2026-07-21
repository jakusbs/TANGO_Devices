#!/bin/sh 

# insert shebang
sed '1s;^;#!/usr/bin/env python3\n;' DoubleInBeckhoff.py > DoubleInBeckhoff
chmod +x DoubleInBeckhoff
mv DoubleInBeckhoff /usr/local/tango_servers

