#!/bin/sh

# insert shebang
sed '1s;^;#!/usr/bin/env python3\n;' Socket.py > Socket
chmod +x Socket
mv Socket /usr/local/tango_servers
