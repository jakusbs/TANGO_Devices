#!/bin/bash
# install_ZI2_DAQ.sh — Install the updated ZI2 Tango device server (dev30933)
# Uses ZI's native Data Acquisition Module for proper averaging.
#
# Usage:
#   1. Copy this script + the Python files to ~/tango-devices/ZI2_DAQ/
#   2. Run: bash install_ZI2_DAQ.sh
#   3. Register in Jive (see instructions at the end)
#   4. Start: ZI2_DAQ <instance_name>
#
# This installs alongside the existing ZI2 device — it does NOT replace it.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEVICE_NAME="ZI2_DAQ"

echo "========================================="
echo " Installing $DEVICE_NAME Tango Device"
echo "========================================="

# ── 1. Check that the required files exist ──────────────────────────
for f in ThreadZI2_DAQ.py ZI2.py; do
    if [ ! -f "$SCRIPT_DIR/$f" ]; then
        echo "ERROR: $f not found in $SCRIPT_DIR"
        echo "Please ensure ThreadZI2_DAQ.py and ZI2.py are present here."
        exit 1
    fi
done

# ── 2. Create the package directory ─────────────────────────────────
echo "Creating package structure..."
mkdir -p "$SCRIPT_DIR/$DEVICE_NAME"

# Copy the device server file as the main module
cp "$SCRIPT_DIR/ZI2.py"             "$SCRIPT_DIR/$DEVICE_NAME/${DEVICE_NAME}.py"
cp "$SCRIPT_DIR/ThreadZI2_DAQ.py"   "$SCRIPT_DIR/$DEVICE_NAME/ThreadZI2.py"

# Create __init__.py that imports main()
cat > "$SCRIPT_DIR/$DEVICE_NAME/__init__.py" << 'EOF'
from .ZI2_DAQ import main
from .ThreadZI2 import ThreadZI2
EOF

# Patch imports in the copied device server:
# - Convert top-level "from ThreadZI2 import ThreadZI2" to a relative import
sed -i 's/^from ThreadZI2 import ThreadZI2$/from .ThreadZI2 import ThreadZI2/' \
    "$SCRIPT_DIR/$DEVICE_NAME/${DEVICE_NAME}.py"

# ── 3. Create setup.py ──────────────────────────────────────────────
cat > "$SCRIPT_DIR/setup.py" << EOF
from setuptools import setup, find_packages

setup(
    name='tangods-${DEVICE_NAME}',
    version='3.0.0',
    description='ZI2 MFLI Tango device (dev30933) with DAQ module averaging',
    packages=['${DEVICE_NAME}'],
    entry_points={
        'console_scripts': [
            '${DEVICE_NAME} = ${DEVICE_NAME}:main',
        ],
    },
    install_requires=[
        'pytango',
        'numpy',
        # EXACT pin: the zhinst client must not be newer than the LabOne
        # data server on the MFLI, or ziDAQServer refuses to connect.
        # Measured 2026-08-12: Green (192.168.1.62) runs 25.04, IR
        # (192.168.1.144) runs 24.10.  25.4.1 matches Green exactly and
        # reaches IR via the device's AllowVersionMismatch property.
        # A range pin let pip jump to 25.10.1, which put Green in FAULT.
        # Re-check with: daq.getString('/zi/about/version')
        'zhinst==25.4.1',
    ],
)
EOF

# ── 4. pip install ──────────────────────────────────────────────────
echo "Installing with pip..."
cd "$SCRIPT_DIR"
pip install . --force-reinstall --quiet

echo ""
echo "========================================="
echo " Installation complete!"
echo "========================================="
echo ""
echo "Next steps:"
echo ""
echo "  The server is ALREADY registered in the Tango DB and this install only"
echo "  replaced the Python package.  Just restart the existing instance:"
echo ""
echo "      ZI2_DAQ ZI2Samba"
echo ""
echo "  which serves device  hpp-N42/measure/ZI2Samba  (class ZI2)."
echo ""
echo "  Do NOT register a new device, and do NOT change the device path in"
echo "  Samba's sensor config.  Earlier versions of this script described a"
echo "  side-by-side migration off the old ZI2/ZI2 server; that server is"
echo "  retired (unexported) and the migration is long done."
echo ""
echo "  The restart is what matters: a running server keeps the modules it"
echo "  imported at startup, so the new code and the pinned zhinst client do"
echo "  not take effect until the process is restarted."
echo ""
echo "  If the device comes up FAULT with a LabOne version mismatch against"
echo "  192.168.1.144, set the device property AllowVersionMismatch = True"
echo "  in Jive and restart.  (Properties are DeviceId, ZI_Host, ZI_Port,"
echo "  ZI_ApiLevel, Harmonics, AllowVersionMismatch — there is no"
echo "  DeviceProxy property; that line was a copy-paste from a"
echo "  socket-based server template.)"
