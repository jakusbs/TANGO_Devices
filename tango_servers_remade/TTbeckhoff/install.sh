#!/bin/bash
DEST=/usr/local/tango_servers/TTbeckhoff
cp TTbeckhoff.py "$DEST"
sed -i '1s|^|#!/usr/bin/env python3\n|' "$DEST"
chmod +x "$DEST"
echo "Installed TTbeckhoff to $DEST"
