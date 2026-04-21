# -*- coding: utf-8 -*-
"""
PyKeithleyPulse
Controls a Keithley 6221 current source in square-wave (pulse) mode via
a Socket TANGO device. This is the companion to PyKeithley/PyKeithley2 —
it uses the same hardware but the delta/pulse waveform instead of sine.

Keithley 6221 square-wave command sequence (from Ref. Manual 622x-901-01):
    SOUR:WAVE:FUNC SQU         — select square wave
    SOUR:WAVE:AMPL <A>         — peak amplitude in A
    SOUR:WAVE:FREQ <f>         — frequency in Hz
    SOUR:WAVE:DCYC 50          — 50 % duty cycle
    SOUR:WAVE:PMAR:STAT ON     — enable phase marker (external trigger)
    SOUR:WAVE:PMAR 180
    SOUR:WAVE:PMAR:OLIN 5      — trigger line 5
    SOUR:WAVE:RANG FIX
    SOUR:WAVE:DUR:TIME INF     — run indefinitely
    SOUR:CURR:COMP <V>         — compliance voltage
    SOUR:WAVE:ARM
    SOUR:WAVE:INIT
"""

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

    def init_device(self):
        Device.init_device(self)
        self._pulse_amplitude = 0.0
        self._pulse_duration  = 0.0
        self._max_amplitude   = 105.0
        self._compliance      = 10.0
        self._autorange       = False
        self._frequency       = 1.0
        self.keithley = tango.DeviceProxy(self.SocketProxy)
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

    @attribute(dtype=float, access=AttrWriteType.READ_WRITE,
               memorized=True, hw_memorized=True,
               unit='s', doc="Pulse duration / half-period in s (informational; use frequency to control timing)")
    def pulseDuration(self):
        return self._pulse_duration

    @pulseDuration.write
    def pulseDuration(self, value):
        self._pulse_duration = value

    @attribute(dtype=float, access=AttrWriteType.WRITE,
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
        self.keithley.Write('CURR:COMP ' + str(value))
        self._compliance = value

    @attribute(dtype=float, access=AttrWriteType.READ_WRITE,
               memorized=True, hw_memorized=True,
               doc="Auto-range enable (0 = off, non-zero = on)")
    def autoRange(self):
        return float(self._autorange)

    @autoRange.write
    def autoRange(self, value):
        self._autorange = bool(value)
        if self._autorange:
            self.keithley.Write('CURR:RANGE:AUTO ON')
        else:
            self.keithley.Write('CURR:RANGE:AUTO OFF')

    @attribute(dtype=float, access=AttrWriteType.READ_WRITE,
               memorized=True, hw_memorized=True,
               unit='Hz', doc="Square-wave frequency in Hz")
    def frequency(self):
        return self._frequency

    @frequency.write
    def frequency(self, value):
        self._frequency = value

    # ---- Commands -------------------------------------------------------

    @command()
    def ON(self):
        """Enable the current output."""
        self.keithley.Write('OUTP ON')

    @command()
    def OFF(self):
        """Disable the current output."""
        self.keithley.Write('OUTP OFF')

    @command()
    def SQUAREWAVE(self):
        """Configure and start square-wave (pulse) output."""
        amp_a = min(self._pulse_amplitude, self._max_amplitude) / 1000.0
        self.keithley.Write('SOUR:WAVE:FUNC SQU')
        self.keithley.Write('SOUR:WAVE:AMPL ' + str(amp_a))
        self.keithley.Write('SOUR:WAVE:FREQ ' + str(self._frequency))
        self.keithley.Write('SOUR:WAVE:DCYC 50')          # 50 % duty cycle
        self.keithley.Write('SOUR:WAVE:PMAR:STAT ON')      # phase marker
        self.keithley.Write('SOUR:WAVE:PMAR 180')
        self.keithley.Write('SOUR:WAVE:PMAR:OLIN 5')       # trigger line 5
        self.keithley.Write('SOUR:WAVE:RANG FIX')
        self.keithley.Write('SOUR:WAVE:DUR:TIME INF')      # run indefinitely
        self.keithley.Write('SOUR:WAVE:ARM')
        self.keithley.Write('SOUR:WAVE:INIT')

    @command()
    def WAVEOFF(self):
        """Abort the current square-wave output."""
        self.keithley.Write('SOUR:WAVE:ABOR')


def main(args=None, **kwargs):
    return run((PyKeithleyPulse,), args=args, **kwargs)


if __name__ == '__main__':
    main()
