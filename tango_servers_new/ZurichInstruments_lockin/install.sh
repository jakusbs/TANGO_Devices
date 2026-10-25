#!/bin/bash
# install.sh — install BOTH MFLI lock-in servers (ZI_DAQ and ZI2_DAQ) from the
# single `zi_lockin` package.
#
# Replaces the former install_ZI_DAQ.sh / install_ZI2_DAQ.sh, which built two
# near-identical packages from two copies of the same code.  The executables,
# the TANGO class names (ZI, ZI2) and the registered instances are unchanged:
#
#     ZI_DAQ  ZISamba     serves hpp-N42/measure/ZISamba   (class ZI,  dev4855)
#     ZI2_DAQ ZI2Samba    serves hpp-N42/measure/ZI2Samba  (class ZI2, dev30933)
#
# Usage:  activate the conda/venv the Tango Starter launches servers from
#         (the one the previous ZI*_DAQ packages were installed into), then
#             bash install.sh
#         and restart the running instance(s).  A running server keeps the
#         modules it imported at startup, so nothing takes effect until the
#         process is restarted.
#
# The zhinst client is pinned EXACTLY (see pyproject.toml) — it must match the
# LabOne version on the instruments.  pytango itself is never reinstalled.

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================="
echo " Installing tangods-zi-lockin (ZI_DAQ + ZI2_DAQ)"
echo "   python: $(command -v python)"
echo "========================================="

# The old per-instrument packages own the same console-script names; remove
# them first so the files on PATH are unambiguously this package's.
for old in tangods-ZI_DAQ tangods-ZI2_DAQ; do
    pip uninstall -y "$old" >/dev/null 2>&1 && echo "removed old package $old" || true
done

# The package itself (never touches pytango: --no-deps), then the pinned
# dependencies without --force-reinstall so an already-correct zhinst stays.
if ! pip install . --no-deps --force-reinstall --quiet; then
    echo "build in isolation failed (no network?) — retrying with the env's setuptools"
    pip install . --no-deps --force-reinstall --no-build-isolation --quiet
fi
pip install --quiet "zhinst==24.10.1" numpy

echo ""
echo "Installed:"
for exe in ZI_DAQ ZI2_DAQ; do
    printf "   %-8s -> %s\n" "$exe" "$(command -v $exe || echo 'NOT ON PATH')"
done
echo ""
echo "Now restart the instance(s) that run on this machine, e.g."
echo "      ZI_DAQ ZISamba        # Green"
echo "      ZI2_DAQ ZI2Samba      # IR"
echo "Do NOT register new devices and do NOT change the device paths in Samba."
echo ""
echo "If a device comes up FAULT with a LabOne version mismatch, set the"
echo "device property AllowVersionMismatch = True in Jive and restart."
echo "(Properties: DeviceId, ZI_Host, ZI_Port, ZI_ApiLevel, Harmonics,"
echo " AllowVersionMismatch.)"
