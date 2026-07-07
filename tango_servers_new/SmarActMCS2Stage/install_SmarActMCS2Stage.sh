#!/bin/bash
# install_SmarActMCS2Stage.sh — Install the SmarActMCS2Stage Tango device server
# MCS2 all-axis stage: wraps the three SmarAct motor axis devices (X/Y/Z) and
# exposes x/y/z position attributes + Stop + Initialise.
#
# Same principle as install_RTV40.sh: generate a setup.py with a console_scripts
# entry point and pip-install, so the server launches as:  SmarActMCS2Stage <instance>
#
# Usage:
#   1. Make sure this script sits next to the package sources
#      (SmarActMCS2Stage.py, __init__.py, __main__.py, release.py).
#   2. Run: bash install_SmarActMCS2Stage.sh
#   3. Register in Jive (see instructions at the end)
#   4. Start: SmarActMCS2Stage <instance_name>

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEVICE_NAME="SmarActMCS2Stage"

echo "========================================="
echo " Installing $DEVICE_NAME Tango Device"
echo "========================================="

# ── 1. Check that the required package files exist ───────────────────
for f in SmarActMCS2Stage.py __init__.py release.py; do
    if [ ! -f "$SCRIPT_DIR/$f" ]; then
        echo "ERROR: $f not found in $SCRIPT_DIR"
        echo "Please run this script from inside the SmarActMCS2Stage package."
        exit 1
    fi
done

# ── 2. Stage a clean build tree ─────────────────────────────────────
# The sources are already laid out as a package, so we copy them into a
# throwaway build dir with a generated setup.py alongside (the package must
# be a *subdirectory* of the dir that holds setup.py).  The build dir is
# removed on exit so nothing extra is left in the source tree.
BUILD_DIR="$SCRIPT_DIR/_install_build"
cleanup() { rm -rf "$BUILD_DIR"; }
trap cleanup EXIT
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR/$DEVICE_NAME"

# Copy only the package's Python modules (skip working/, __pycache__, etc.)
cp "$SCRIPT_DIR"/*.py "$BUILD_DIR/$DEVICE_NAME/"

# ── 3. Create setup.py ──────────────────────────────────────────────
cat > "$BUILD_DIR/setup.py" << EOF
from setuptools import setup

setup(
    name='tangods-${DEVICE_NAME,,}',
    version='1.0.0',
    description='SmarAct MCS2 all-axis stage Tango device server',
    packages=['${DEVICE_NAME}'],
    entry_points={
        'console_scripts': [
            '${DEVICE_NAME} = ${DEVICE_NAME}:main',
        ],
    },
    install_requires=[
        'pytango',
    ],
)
EOF

# ── 4. pip install ──────────────────────────────────────────────────
echo "Installing with pip..."
cd "$BUILD_DIR"
pip install . --force-reinstall --quiet

echo ""
echo "========================================="
echo " Installation complete!"
echo "========================================="
echo ""
echo "Next steps:"
echo ""
echo "  1. Register in Jive:"
echo "     Server:   ${DEVICE_NAME}/<instance>"
echo "     Class:    SmarActMCS2Stage"
echo "     Device:   smaract2/control/IR-controller  (or whatever you prefer)"
echo ""
echo "  2. Set device properties (the three underlying motor axis devices):"
echo "     XMotorDevice = smaract2/mcs2/x"
echo "     YMotorDevice = smaract2/mcs2/y"
echo "     ZMotorDevice = smaract2/mcs2/z"
echo "     MovementTimeout = 30   (class property, optional)"
echo ""
echo "  3. Start the server:"
echo "     ${DEVICE_NAME} <instance>"
echo ""
echo "  4. Commands: x/y/z position attributes, Stop, and Initialise"
echo "     (Initialise sends Init to each motor axis — the fix for a wedged"
echo "      axis after manual hand-controller use)."
