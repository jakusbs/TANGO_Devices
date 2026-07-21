#!/usr/bin/env bash
#
# install_vimba6.sh — Intermag lab Vimba camera software installer
#
# Removes any Vimba X install (the 2026-1 release broke the viewer on all
# machines, July 2026) and sets up the known-good classic Vimba 6.0:
#   * /opt/Vimba_6_0 (copied from this repo if not already present)
#   * GigE transport layer registered (GENICAM_GENTL64_PATH)
#   * desktop launcher with icon ("Vimba Viewer") for the invoking user
#   * `vimba` terminal alias
#
# Usage:  sudo bash install_vimba6.sh
# Run it from its own directory inside a checkout/copy of TANGO_Devices
# (it copies Vimba_6_0/ from next to itself). Log out/in (better: reboot)
# afterwards so the clean GENICAM_GENTL64_PATH takes effect everywhere.
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$SCRIPT_DIR/Vimba_6_0"
DEST=/opt/Vimba_6_0

if [ "$(id -u)" -ne 0 ]; then
    echo "Please run with sudo: sudo bash $0" >&2
    exit 1
fi

# The desktop launcher and alias belong to the human, not root.
REAL_USER="${SUDO_USER:-root}"
REAL_HOME="$(getent passwd "$REAL_USER" | cut -d: -f6)"

echo "== 1/5  Stopping any running Vimba applications"
pkill -f "VimbaXViewer" 2>/dev/null || true
pkill -f "VimbaViewer"  2>/dev/null || true
sleep 1

echo "== 2/5  Removing Vimba X"
rm -rf /opt/VimbaX_*
rm -f  /etc/profile.d/VimbaX_*.sh
rm -f  /usr/share/applications/vimbax*.desktop
rm -f  "$REAL_HOME/.local/share/applications/"vimbax*.desktop
# drop any shell lines referencing the removed install (old aliases/exports)
if [ -f "$REAL_HOME/.bashrc" ]; then
    sed -i '/VimbaX/d' "$REAL_HOME/.bashrc"
fi

echo "== 3/5  Installing Vimba 6.0 to $DEST"
if [ -d "$DEST" ]; then
    echo "    $DEST already exists — keeping it (delete it first to force a fresh copy)"
else
    [ -d "$SRC" ] || { echo "Source $SRC not found — run from the repo directory" >&2; exit 1; }
    cp -a "$SRC" "$DEST"
fi
# restore executable bits (lost if the repo was fetched as a GitHub ZIP)
find "$DEST" -name "*.sh" -exec chmod +x {} +
find "$DEST" -type f \( -name "VimbaViewer" -o -name "*.so" -o -name "*.so.*" -o -name "*.cti" \) -exec chmod +x {} +

echo "== 4/5  Registering the GigE transport layer"
bash "$DEST/VimbaGigETL/Install.sh"

echo "== 5/5  Desktop launcher + 'vimba' alias for $REAL_USER"
APPS_DIR="$REAL_HOME/.local/share/applications"
mkdir -p "$APPS_DIR"
cat > "$APPS_DIR/vimba-viewer.desktop" << EOF
[Desktop Entry]
Type=Application
Name=Vimba Viewer
Comment=Allied Vision Manta camera viewer
Exec=env GENICAM_GENTL64_PATH=$DEST/VimbaGigETL/CTI/x86_64bit $DEST/Tools/Viewer/Bin/x86_64bit/VimbaViewer
Path=$DEST/Tools/Viewer/Bin/x86_64bit
Icon=$DEST/VimbaCPP/Examples/VimbaViewer/Source/Images/stripes_256.png
Terminal=false
Categories=Graphics;
StartupWMClass=VimbaViewer
EOF
chown -R "$REAL_USER:" "$APPS_DIR/vimba-viewer.desktop"

if [ -f "$REAL_HOME/.bashrc" ]; then
    sed -i '/^alias vimba=/d' "$REAL_HOME/.bashrc"
    printf "alias vimba='GENICAM_GENTL64_PATH=%s/VimbaGigETL/CTI/x86_64bit %s/Tools/Viewer/Bin/x86_64bit/VimbaViewer >/dev/null 2>&1 &'\n" \
        "$DEST" "$DEST" >> "$REAL_HOME/.bashrc"
fi

echo
echo "Done. Log out and back in (better: reboot) so the cleaned"
echo "GENICAM_GENTL64_PATH takes effect in every session."
echo "Launch: 'Vimba Viewer' in the app grid, or 'vimba' in a terminal."
echo "Reminder: a GigE camera accepts ONE controlling application at a"
echo "time — close viewers when done, or other PCs cannot open the camera."
