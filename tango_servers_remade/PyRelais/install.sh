#!/bin/sh

# insert shebang
sed '1s;^;#!/usr/bin/env python3\n;' PyRelais.py > PyRelais
chmod +x PyRelais
mv PyRelais /usr/local/tango_servers
