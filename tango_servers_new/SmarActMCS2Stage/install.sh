#!/bin/bash
# install.sh — install the SmarActMCS2Stage Tango device server.
#
# Installs via pip + a console_scripts entry point (the same style as
# install_ZI2_DAQ.sh), so the `SmarActMCS2Stage` executable lands in the
# ACTIVE Python environment's bin/ (on PATH) — NOT in a hardcoded folder.
#
# The old version of this script did `mv SmarActMCS2Stage /usr/local/tango_servers`,
# which is wrong on the MCS2 computer: its Tango-server folder is elsewhere, so
# the Starter kept launching the previously-installed binary and the new code
# (Initialise / Home / SetZero fixes) never actually ran.  pip install avoids
# any hardcoded path.
#
# Usage:
#   1. Make sure the correct conda/venv is ACTIVE — the same environment the
#      Tango Starter uses to launch the MCS2 servers (the one ZI2_DAQ went into).
#   2. Run: bash install.sh
#   3. Restart the server from Astor/Starter, or:  SmarActMCS2Stage <instance>

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEVICE_NAME="SmarActMCS2Stage"

echo "========================================="
echo " Installing $DEVICE_NAME Tango Device"
echo "========================================="

# ── 1. Check that the required source file exists ───────────────────
if [ ! -f "$SCRIPT_DIR/${DEVICE_NAME}.py" ]; then
    echo "ERROR: ${DEVICE_NAME}.py not found in $SCRIPT_DIR"
    exit 1
fi

echo "Using python: $(command -v python3)"
echo "Using pip:    $(command -v pip)"

# ── 2. Build a clean package layout for pip ─────────────────────────
BUILD="$SCRIPT_DIR/.pipbuild"
rm -rf "$BUILD"
mkdir -p "$BUILD/$DEVICE_NAME"

cp "$SCRIPT_DIR/${DEVICE_NAME}.py" "$BUILD/$DEVICE_NAME/${DEVICE_NAME}.py"

cat > "$BUILD/$DEVICE_NAME/__init__.py" << EOF
from .${DEVICE_NAME} import ${DEVICE_NAME}, main
EOF

# ── 3. Create setup.py with the console_scripts entry point ─────────
cat > "$BUILD/setup.py" << EOF
from setuptools import setup

setup(
    name='tangods-smaractmcs2stage',
    version='1.1.0',
    description='MCS2 all-axis stage Tango device (X/Y/Z + Initialise/Home/SetZero)',
    packages=['${DEVICE_NAME}'],
    entry_points={
        'console_scripts': [
            '${DEVICE_NAME} = ${DEVICE_NAME}:main',
        ],
    },
    install_requires=['pytango'],
)
EOF

# ── 4. pip install into the active environment ──────────────────────
# --no-deps: don't touch the environment's existing pytango (already present on
# any Tango machine); --force-reinstall: replace even at the same version.
echo "Installing with pip into the active environment..."
cd "$BUILD"
pip install . --force-reinstall --no-deps --quiet
cd "$SCRIPT_DIR"
rm -rf "$BUILD"

INSTALLED="$(command -v ${DEVICE_NAME} || true)"

echo ""
echo "========================================="
echo " Installation complete!"
echo "========================================="
echo ""
echo "  Entry point: ${INSTALLED:-<not on PATH — is the right env active?>}"
echo ""
echo "Next steps:"
echo ""
echo "  1. If an OLD copy exists at /usr/local/tango_servers/${DEVICE_NAME}"
echo "     (from the previous install.sh), delete it so PATH resolves to the"
echo "     freshly pip-installed entry point:"
echo "         rm -f /usr/local/tango_servers/${DEVICE_NAME}"
echo ""
echo "  2. Restart the server (Astor/Starter, or from a shell):"
echo "         ${DEVICE_NAME} <instance>"
echo ""
echo "  3. Verify the new commands are present (Jive -> the stage device):"
echo "         Initialise, Home, SetZero"
echo ""
echo "  The Jive registration (Server ${DEVICE_NAME}/<instance>, Class"
echo "  ${DEVICE_NAME}) is unchanged — this only replaces the executable."
