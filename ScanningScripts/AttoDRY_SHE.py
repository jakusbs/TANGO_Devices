# -*- coding: utf-8 -*-
# AttoDRY_SHE.py
# SHE measurement using the AttoDRY superconducting magnet.
# Repeats N cycles of +, -, -, + field polarity, running one scan per step.
# Field is set via AttoDRY MagneticField attribute; polarity flip takes ~60 s.

import PyTango
import time
import shutil
import math
from collections import deque

#########################################################################
# Configuration

filepath = "/home/intermag/Data2/Scanlists/"
filename = filepath + "20260518_SAMPLE_SHE_AttoDRY.txt"

# Field magnitude (T) - script applies +field and -field
FieldMagnitude = 0.3  # T

# Number of +,-,-,+ cycles
Cycles = 2

# AC current source settings
frequency = 8751.17   # Hz
amplitude = 6.5e-3    # A  (mA in Keithley attribute, so 6.5e-3 = 6.5 mA)
current_range = "20mA"

# Wait after field settles before starting scan (s)
extra_wait_after_settle = 60.0  # superconducting magnet needs time after ramp

# Mirror copy path - leave empty string to skip
serverpath = "/mnt/trmoke/"
mirrorpath = serverpath + "Scanning/Data/Scanlists_S2/"

# Tango Device Proxies
Scan     = PyTango.DeviceProxy("hpp-n42/scanserver/scanserver2")
Magnet   = PyTango.DeviceProxy("hpp-n42/attodry/attodry")
Keithley = PyTango.DeviceProxy("hpp-N42/current/PyKeithley2")

#########################################################################
# Settle parameters (tune if needed)
SETTLE_TOL        = 5e-3   # |mean - target| threshold (T)
SETTLE_AVG_TIME   = 3.0    # moving-average window (s)
SETTLE_DRIFT_TOL  = 5e-3   # max spread inside window (T)
SETTLE_POLL       = 0.1    # poll interval (s)
SETTLE_MAX_WAIT   = 600.0  # hard timeout (s)

#########################################################################


def _read_field():
    return float(Magnet.read_attribute("MagneticField").value)


def sweep_and_wait(field):
    """Ramp to field (T) and block until the moving average has settled."""

    def wait_for_settle(target):
        window = deque()
        sum_v = 0.0
        min_v = max_v = None
        t_start = time.time()

        while True:
            v = _read_field()
            t = time.time()
            window.append((t, v))
            sum_v += v
            if min_v is None or v < min_v: min_v = v
            if max_v is None or v > max_v: max_v = v

            cutoff = t - SETTLE_AVG_TIME
            while window and window[0][0] < cutoff:
                t0, v0 = window.popleft()
                sum_v -= v0
                if v0 in (min_v, max_v):
                    vals = [vv for (_, vv) in window] or [v]
                    min_v, max_v = min(vals), max(vals)

            span = (max_v - min_v) if min_v is not None else float('inf')
            if window and (window[-1][0] - window[0][0] >= max(0.5 * SETTLE_AVG_TIME, SETTLE_POLL)):
                mean_v = sum_v / len(window)
                if abs(mean_v - target) <= SETTLE_TOL and span <= SETTLE_DRIFT_TOL:
                    print("  Settled: mean=%.4f T, |err|=%.4g T, span=%.4g T"
                          % (mean_v, abs(mean_v - target), span))
                    return mean_v

            if (time.time() - t_start) > SETTLE_MAX_WAIT:
                raise RuntimeError("Timeout waiting for field to settle at %.4f T" % target)

            time.sleep(SETTLE_POLL)

    Magnet.write_attribute("MagneticField", field)
    now = _read_field()
    print("  Ramping to %.4f T  (delta = %.1f mT)" % (field, abs(now - field) * 1e3))
    val = wait_for_settle(field)
    if extra_wait_after_settle > 0:
        print("  Extra wait %.0f s after settle ..." % extra_wait_after_settle)
        time.sleep(extra_wait_after_settle)
    return val


def set_current():
    Keithley.OFF()
    time.sleep(0.1)
    Keithley.write_attribute("range", current_range)
    time.sleep(0.1)
    Keithley.write_attribute("frequency", frequency)
    time.sleep(0.1)
    Keithley.write_attribute("amplitude", amplitude)
    time.sleep(0.1)
    Keithley.ON()
    print("  Keithley: %.4f mA @ %.2f Hz, range=%s" % (amplitude * 1e3, frequency, current_range))


def startScan():
    try:
        Scan.Start()
        time.sleep(1)
        while Scan.State() != PyTango.DevState.MOVING:
            time.sleep(1)
        print("  Scan started")
    except Exception as e:
        print("startScan(): " + str(e))
        exit()


def is_Scan_done():
    timeouts = 0
    done = False
    while not done and timeouts < 10:
        try:
            state = Scan.State()
            done = state != PyTango.DevState.MOVING
            if state == PyTango.DevState.FAULT:
                print("Scanserver FAULT - aborting")
                exit()
        except Exception as e:
            print("Scanserver state timeout: " + str(e))
            done = False
            timeouts += 1
        time.sleep(2)
    if timeouts == 10:
        print("10 consecutive timeouts from scanserver - aborting")
        exit()


def writeFileName(scan_name, pol_label):
    with open(filename, "a") as f:
        f.write(scan_name + "\t" + pol_label + "\n")
        f.flush()


def mirrorScanlist():
    if not mirrorpath:
        return
    try:
        shutil.copyfile(filename, mirrorpath + name)
    except Exception as e:
        print("*** Mirror copy failed: " + str(e) + " ***")


#########################################################################
# Main sequence
#########################################################################

name = filename.split('/')[-1]
print('\n\n*** AttoDRY SHE sequence: ' + name + ' ***\n')
print('Field: +/-%.4f T,  Cycles: %d\n' % (FieldMagnitude, Cycles))

# Verify AttoDRY is reachable
try:
    _read_field()
except Exception as e:
    print("AttoDRY not reachable: " + str(e))
    exit()

# Set up Keithley once - stays on throughout
set_current()

for n in range(Cycles):
    try:
        print("\n*** Cycle %d / %d ***" % (n + 1, Cycles))

        # +field
        print("\n[+] Positive field")
        sweep_and_wait(+FieldMagnitude)
        startScan()
        writeFileName(str(Scan.generatedNexusFileName), "+%.4fT" % FieldMagnitude)
        is_Scan_done()
        print("  Done: " + str(Scan.generatedNexusFileName))
        mirrorScanlist()

        # -field  (first)
        print("\n[-] Negative field (1st)")
        sweep_and_wait(-FieldMagnitude)
        startScan()
        writeFileName(str(Scan.generatedNexusFileName), "-%.4fT" % FieldMagnitude)
        is_Scan_done()
        print("  Done: " + str(Scan.generatedNexusFileName))
        mirrorScanlist()

        # -field  (second)
        print("\n[-] Negative field (2nd)")
        sweep_and_wait(-FieldMagnitude)
        startScan()
        writeFileName(str(Scan.generatedNexusFileName), "-%.4fT" % FieldMagnitude)
        is_Scan_done()
        print("  Done: " + str(Scan.generatedNexusFileName))
        mirrorScanlist()

        # +field  (second)
        print("\n[+] Positive field (2nd)")
        sweep_and_wait(+FieldMagnitude)
        startScan()
        writeFileName(str(Scan.generatedNexusFileName), "+%.4fT" % FieldMagnitude)
        is_Scan_done()
        print("  Done: " + str(Scan.generatedNexusFileName))
        mirrorScanlist()

    except KeyboardInterrupt:
        print('\n*** Keyboard interrupt - waiting for current scan to finish ...')
        is_Scan_done()
        print("Last scan: " + str(Scan.generatedNexusFileName))
        mirrorScanlist()
        print("*** Sequence stopped by user ***\n")
        Keithley.OFF()
        exit()

    except Exception as e:
        print("*** Error in cycle %d: %s ***" % (n + 1, str(e)))
        Keithley.OFF()
        raise

print("\n*** Sequence finished: " + filename + " ***\n")
Keithley.OFF()
# Leave magnet at last field - caller decides whether to ramp to zero
