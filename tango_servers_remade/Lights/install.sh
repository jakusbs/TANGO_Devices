#!/bin/sh

# insert shebang
sed '1s;^;#!/usr/bin/env python3\n;' Lights.py > Lights
chmod +x Lights
mv Lights /usr/local/tango_servers
