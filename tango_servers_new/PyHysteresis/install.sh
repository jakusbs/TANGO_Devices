#!/bin/sh

# PyHysteresis is split across two files:
#   PyHysteresis.py     — the TANGO device (entry point, gets the shebang)
#   HysteresisThread.py — the measurement thread, imported via
#                         `from HysteresisThread import *`
# BOTH must be deployed to /usr/local/tango_servers, otherwise the new device
# ends up importing a stale HysteresisThread next to it — the per-cycle
# retention (_cyc) silently stops working and GetNumberOfCycles returns 0.

DEST=/usr/local/tango_servers

# entry point — insert shebang, make executable
sed '1s;^;#!/usr/bin/env python3\n;' PyHysteresis.py > PyHysteresis
chmod +x PyHysteresis
mv PyHysteresis "$DEST"

# companion module — plain importable module, no shebang
cp HysteresisThread.py "$DEST/HysteresisThread.py"

# nuke any stale bytecode so a leftover .pyc can't shadow the fresh source
rm -f "$DEST/HysteresisThread.pyc"
rm -rf "$DEST/__pycache__"

echo "Deployed PyHysteresis + HysteresisThread to $DEST"
echo "NOTE: fully restart the device-server process (a TANGO 'Init' does not reload Python code)."
