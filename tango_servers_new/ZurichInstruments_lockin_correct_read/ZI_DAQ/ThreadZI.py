# File:             ThreadZI.py
# author:           P. Noel, C. Murer (original)
#
# v5.0 — modern tango.server companion: reads DeviceId from parent, writes
#         results into parent._x / parent._y so the new attribute getters
#         pick them up. Settling is NOT done here — Samba waits before Start().

import threading
import tango
import numpy as np

MIN_COLLECT = 0.05   # minimum collection window (seconds)


class ThreadZI(threading.Thread):
    lock = threading.Lock()

    def __init__(self, parent):
        threading.Thread.__init__(self)
        self.p = parent
        self.daemon = True

    def run(self):
        self.p.set_state(tango.DevState.RUNNING)

        try:
            if self.p.daq is None:
                self.p.error_stream('ThreadZI: daq is None, aborting')
                self.p.set_state(tango.DevState.FAULT)
                return

            device = self.p.DeviceId
            collect_time = max(self.p._integrationtime, MIN_COLLECT)
            timeout_ms   = int((collect_time + 5.0) * 1000)

            with self.p._daq_lock:
                daq = self.p.daq
                # Wake up the data server if it went idle between measurements.
                # Without a prior API call, a cold server + short collect window
                # returns an empty dict → all values silently become 0.
                daq.getDouble('/{}/demods/0/rate'.format(device))
                # Flush stale/transient samples from the settling period
                daq.poll(0.01, 100, 0, True)
                # Collect for the integration window
                data = daq.poll(collect_time, timeout_ms, 0, True)

            sqrt2 = np.sqrt(2)
            missing = []
            for i in range(4):
                path = '/{}/demods/{}/sample'.format(device, i)
                for comp, store in (('x', self.p._x), ('y', self.p._y)):
                    try:
                        samples = data[path][comp]
                        store[i] = float(np.mean(samples)) * 1e6 * sqrt2
                    except (KeyError, TypeError, ValueError):
                        # NaN, not 0.0: no samples means nothing was measured,
                        # and 0 is indistinguishable from a genuinely nulled
                        # balanced-diode signal, so the scan engine would
                        # record it as a valid measurement.
                        store[i] = np.nan
                        missing.append('{}/{}'.format(i, comp))

            if missing:
                self.p.warn_stream(
                    'ZI: poll returned no samples for demod(s): {} '
                    '— values set to NaN (server was idle?)'.format(', '.join(missing)))

            self.p._last_collect_s = collect_time
            self.p.info_stream(
                'ZI: polled {:.3f}s, numpy avg'.format(collect_time))

        except Exception as e:
            # End in FAULT, not ON: a clean RUNNING->ON transition after a
            # failed acquisition makes the scan engine read stale values as
            # a successful point. Recover via the Reconnect command.
            try:
                self.p.error_stream('ThreadZI error: {}'.format(e))
                self.p.set_state(tango.DevState.FAULT)
                self.p.set_status('Acquisition failed: {}'.format(e))
            except Exception:
                pass
            return

        self.p.set_state(tango.DevState.ON)

    def stop(self):
        self.p.set_state(tango.DevState.ON)
