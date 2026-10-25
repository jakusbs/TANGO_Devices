# zi_lockin/thread.py — one integration cycle of an MFLI lock-in.
#
# Originally ThreadZI.py / ThreadZI2.py (P. Noel, C. Murer); the two files
# differed only in their class name and log prefixes.  The prefix is now the
# parent device's class name, so the log lines read exactly as before
# ("ZI: polled …" on the Green server, "ZI2: polled …" on the IR one).
#
# Settling is NOT done here — Samba waits for `settlingtime` before Start().

import threading

import numpy as np
import tango

MIN_COLLECT = 0.05   # minimum collection window (seconds)


class AcquisitionThread(threading.Thread):
    """Flush, collect for `integrationtime`, average, store into the parent.

    Runs under the parent's ``_daq_lock`` for the whole poll, so attribute
    reads that take the lock non-blocking return their cached value instead
    of racing the C extension (ziDAQServer is not thread-safe).
    """

    def __init__(self, parent):
        threading.Thread.__init__(self)
        self.p = parent
        self.daemon = True

    @property
    def _tag(self):
        return type(self.p).__name__

    def run(self):
        self.p.set_state(tango.DevState.RUNNING)

        try:
            if self.p.daq is None:
                self.p.error_stream('Thread{}: daq is None, aborting'.format(self._tag))
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
                    '{}: poll returned no samples for demod(s): {} '
                    '— values set to NaN (server was idle?)'.format(
                        self._tag, ', '.join(missing)))

            self.p._last_collect_s = collect_time
            self.p.info_stream(
                '{}: polled {:.3f}s, numpy avg'.format(self._tag, collect_time))

        except Exception as e:
            # End in FAULT, not ON: a clean RUNNING->ON transition after a
            # failed acquisition makes the scan engine read stale values as
            # a successful point. Recover via the Reconnect command.
            try:
                self.p.error_stream('Thread{} error: {}'.format(self._tag, e))
                self.p.set_state(tango.DevState.FAULT)
                self.p.set_status('Acquisition failed: {}'.format(e))
            except Exception:
                pass
            return

        self.p.set_state(tango.DevState.ON)

    def stop(self):
        self.p.set_state(tango.DevState.ON)
