#!/bin/sh
# install.sh — install the SmarActMCS2Stage Tango device server.
# Prepends a shebang, makes it executable and copies it to the standard
# install location.  SmarActMCS2Stage.py is self-contained (no relative
# imports), so the single file runs directly:  SmarActMCS2Stage <instance>

# insert shebang
sed '1s;^;#!/usr/bin/env python3\n;' SmarActMCS2Stage.py > SmarActMCS2Stage
chmod +x SmarActMCS2Stage
mv SmarActMCS2Stage /usr/local/tango_servers
