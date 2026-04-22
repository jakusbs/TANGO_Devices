#!/bin/sh

# insert shebang
sed '1s;^;#!/usr/bin/env python3\n;' DoubleInBeckhoffAverage.py > DoubleInBeckhoffAverage
chmod +x DoubleInBeckhoffAverage
mv DoubleInBeckhoffAverage /usr/local/tango_servers
