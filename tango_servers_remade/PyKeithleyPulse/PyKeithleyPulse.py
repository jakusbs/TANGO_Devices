# -*- coding: utf-8 -*-
"""
PyKeithleyPulse
Controls a Keithley 6221 current source in square-wave (pulse) mode via
a Socket TANGO device. This is the companion to PyKeithley/PyKeithley2 —
it uses the same hardware but the delta/pulse waveform instead of sine.

Keithley 6221 square-wave command sequence (from Ref. Manual 622x-901-01):
    SOUR:WAVE:ABOR              — ensure IDLE state before configuration
    SOUR:WAVE:FUNC SQU         — select square wave
    SOUR:WAVE:AMPL <A>         — peak amplitude in A
    SOUR:WAVE:FREQ <f>         — frequency in Hz
    SOUR:WAVE:DCYC 50          — 50 % duty cycle
    SOUR:WAVE:PMAR:STAT ON     — enable phase marker (external trigger)
    SOUR:WAVE:PMAR 180
    SOUR:WAVE:PMAR:OLIN 5      — trigger line 5
    SOUR:WAVE:RANG FIX
    SOUR:WAVE:DUR:TIME INF     — run indefinitely
    CURR:COMP <V>              — compliance voltage
    <100 ms pause>             — empirically required before ARM
    SOUR:WAVE:ARM
    SOUR:WAVE:INIT
"""

import time

import tango
from tango import DevState, AttrWriteType
from tango.server import Device, command, attribute, device_property, run

__all__ = ["PyKeithleyPulse", "main"]


class PyKeithleyPulse(Device):
    """
    Keithley 6221 square-wave (pulse) generator.
    Amplitude and compliance are in mA and V respectively.
    Frequency is in Hz, pulse duration in s (stored but not sent separately —
    set frequency to control period).

    **Properties:**
    - SocketProxy: TANGO path to the Socket device connected to the Keithley
    """

    SocketProxy = device_property(
        dtype='str',
        default_value='hpp-n42/socket/keithley6221',
        doc="TANGO path to the Socket device for the Keithley"
    )

    _RANGE_MAP = {
        '0.0002mA': '2e-7', '0.002mA': '2e-6', '0.02mA': '2e-5',
        '0.2mA': '2e-4', '2mA': '0.002', '20mA': '0.02', '100mA': '0.1',
    }

    def init_device(self):
        Device.init_device(self)
        self._pulse_amplitude = 0.0
        self._max_amplitude   = 105.0
        self._compliance      = 10.0
        self._autorange       = False
        self._frequency       = 1.0
        self._range           = '100mA'
        self._wave_running    = False
        self.keithley = tango.DeviceProxy(self.SocketProxy)
        # Recover from any state left by a previous session (instrument keeps
        # running waveforms across TCP disconnects). ABOR is safe in IDLE state.
        try:
            self.keithley.WriteLine('SOUR:WAVE:ABOR')
            self.keithley.WriteLine('OUTP OFF')
        except Exception:
            pass
        self.set_state(DevState.ON)

    def always_executed_hook(self):
        pass

    # ---- Attributes -----------------------------------------------------

    @attribute(dtype=float, access=AttrWriteType.READ_WRITE,
               memorized=True, hw_memorized=True,
               unit='mA', doc="Square-wave peak amplitude in mA (clamped to maxAmplitude)")
    def pulseAmplitude(self):
        return self._pulse_amplitude

    @pulseAmplitude.write
    def pulseAmplitude(self, value):
        self._pulse_amplitude = min(abs(value), self._max_amplitude)
        if self._wave_running:
            self._rearm()

    @attribute(dtype=float, access=AttrWriteType.READ_WRITE,
               unit='s', doc="Pulse half-period in s; writing updates frequency (= 1 / (2 * duration))")
    def pulseDuration(self):
        return 1.0 / (2.0 * self._frequency)

    @pulseDuration.write
    def pulseDuration(self, value):
        if value <= 0:
            tango.Except.throw_exception(
                "Invalid pulseDuration",
                "pulseDuration must be > 0 s",
                "PyKeithleyPulse::pulseDuration")
        self._frequency = 1.0 / (2.0 * value)
        if self._wave_running:
            self._rearm()

    @attribute(dtype=float, access=AttrWriteType.READ_WRITE,
               memorized=True, hw_memorized=False,
               unit='mA', doc="Maximum allowed pulse amplitude in mA")
    def maxAmplitude(self):
        return self._max_amplitude

    @maxAmplitude.write
    def maxAmplitude(self, value):
        self._max_amplitude = abs(value)

    @attribute(dtype=float, access=AttrWriteType.READ_WRITE,
               memorized=True, hw_memorized=True,
               unit='V', doc="Compliance voltage in V (0.1–105 V)")
    def compliance(self):
        return self._compliance

    @compliance.write
    def compliance(self, value):
        if value < 0.1:
            value = 0.1
        if value > 105.0:
            value = 105.0
        self._compliance = value
        if self._wave_running:
            self._rearm()
        else:
            self.keithley.WriteLine('CURR:COMP ' + str(value))

    @attribute(dtype=float, access=AttrWriteType.READ_WRITE,
               memorized=True, hw_memorized=True,
               doc="Auto-range enable (0 = off, non-zero = on)")
    def autoRange(self):
        return float(self._autorange)

    @autoRange.write
    def autoRange(self, value):
        self._autorange = bool(value)
        if self._wave_running:
            self._rearm()
        else:
            if self._autorange:
                self.keithley.WriteLine('CURR:RANGE:AUTO ON')
            else:
                self.keithley.WriteLine('CURR:RANGE:AUTO OFF')

    @attribute(dtype=float, access=AttrWriteType.READ_WRITE,
               memorized=True, hw_memorized=True,
               unit='Hz', doc="Square-wave frequency in Hz")
    def frequency(self):
        return self._frequency

    @frequency.write
    def frequency(self, value):
        self._frequency = value
        if self._wave_running:
            self._rearm()

    @attribute(dtype=str, access=AttrWriteType.READ_WRITE,
               memorized=True, hw_memorized=True,
               doc="Current range: 0.0002mA, 0.002mA, 0.02mA, 0.2mA, 2mA, 20mA, 100mA")
    def range(self):
        return self._range

    @range.write
    def range(self, value):
        if value not in self._RANGE_MAP:
            tango.Except.throw_exception(
                "Invalid range",
                "Valid ranges: " + ', '.join(self._RANGE_MAP.keys()),
                "PyKeithleyPulse::range")
        self._range = value
        if self._wave_running:
            self._rearm()
        elif not self._autorange:
            self.keithley.WriteLine('CURR:RANGE ' + self._RANGE_MAP[value])

    # ---- Commands -------------------------------------------------------

    def _rearm(self):
        """Abort, reconfigure, and restart the square wave with current parameters."""
        amp_a = min(self._pulse_amplitude, self._max_amplitude) / 1000.0
        self.keithley.WriteLine('SOUR:WAVE:ABOR')
        self.keithley.WriteLine('SOUR:WAVE:FUNC SQU')
        self.keithley.WriteLine('SOUR:WAVE:AMPL ' + str(amp_a))
        self.keithley.WriteLine('SOUR:WAVE:FREQ ' + str(self._frequency))
        self.keithley.WriteLine('SOUR:WAVE:DCYC 50')
        self.keithley.WriteLine('CURR:COMP ' + str(self._compliance))
        if self._autorange:
            self.keithley.WriteLine('CURR:RANGE:AUTO ON')
        else:
            self.keithley.WriteLine('CURR:RANGE:AUTO OFF')
            self.keithley.WriteLine('CURR:RANGE ' + self._RANGE_MAP[self._range])
        self.keithley.WriteLine('SOUR:WAVE:PMAR:STAT ON')
        self.keithley.WriteLine('SOUR:WAVE:PMAR 180')
        self.keithley.WriteLine('SOUR:WAVE:PMAR:OLIN 5')
        self.keithley.WriteLine('SOUR:WAVE:RANG FIX')
        self.keithley.WriteLine('SOUR:WAVE:DUR:TIME INF')
        time.sleep(0.1)
        self.keithley.WriteLine('SOUR:WAVE:ARM')
        self.keithley.WriteLine('SOUR:WAVE:INIT')

    @command()
    def ON(self):
        """Enable the current output."""
        self.keithley.WriteLine('OUTP ON')

    @command()
    def OFF(self):
        """Disable the current output."""
        self.keithley.WriteLine('OUTP OFF')
        self._wave_running = False

    @command()
    def SQUAREWAVE(self):
        """Configure and start square-wave (pulse) output."""
        self._rearm()
        self._wave_running = True

    @command()
    def WAVEOFF(self):
        """Abort the current square-wave output."""
        self.keithley.WriteLine('SOUR:WAVE:ABOR')
        self._wave_running = False


def main(args=None, **kwargs):
    return run((PyKeithleyPulse,), args=args, **kwargs)


if __name__ == '__main__':
    main()
