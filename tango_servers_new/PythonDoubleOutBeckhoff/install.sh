#!/bin/sh 

# insert shebang
sed '1s;^;#!/usr/bin/env python3\n;' DoubleOutBeckhoff.py > DoubleOutBeckhoff
chmod +x DoubleOutBeckhoff
mv DoubleOutBeckhoff /usr/local/tango_servers

