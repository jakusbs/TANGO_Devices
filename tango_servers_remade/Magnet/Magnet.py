# -*- coding: utf-8 -*-
"""
Magnet
Controls a dual electromagnet (polar + longitudinal) via Beckhoff DAC outputs
through an AdsBridge2 proxy. Hall probes on dedicated ADC inputs measure the
actual field. Correction factors scale the Hall-probe reading.
"""

import tango
from tango import DevState, AttrWriteType
from tango.server import Device, command, attribute, device_property, run

__all__ = ["Magnet", "main"]

# Beckhoff analog output range — same DAC family ANM200 guards at ±10 V.
DAC_LIMIT_V = 10.0


class Magnet(Device):
    """
    Dual electromagnet controller (polar + longitudinal geometry).
    Currents are set in Ampere; the device converts to Volts using
    AmperePerVolt. Field readback is in mT from the Hall probe.

    **Properties:**
    - AdsBridge: TANGO path to AdsBridge2 device
    - AmperePerVolt_polar/longitudinal: calibration factor [A/V]
    - BeckhoffVariable_polar/longitudinal: DAC output PLC variable names
    - BeckhoffVariable_polarfield/longitudinalfield: ADC input PLC variable names
    - HallSensitivity_polar/longitudinal: Hall probe sensitivity [V/T]
    """

    AdsBridge = device_property(
        dtype='str', default_value='hpp-n42/beckhoff/adsBridge2',
        doc="TANGO path to AdsBridge2 device"
    )
    AmperePerVolt_polar = device_property(
        dtype=float, default_value=1.0,
        doc="Calibration: Ampere per Volt for polar coil [A/V]"
    )
    AmperePerVolt_longitudinal = device_property(
        dtype=float, default_value=1.0,
        doc="Calibration: Ampere per Volt for longitudinal coil [A/V]"
    )
    BeckhoffVariable_polar = device_property(
        dtype='str', default_value='MAIN.AnalogOut2',
        doc="PLC LREAL variable for polar DAC output"
    )
    BeckhoffVariable_longitudinal = device_property(
        dtype='str', default_value='MAIN.AnalogOut1',
        doc="PLC LREAL variable for longitudinal DAC output"
    )
    BeckhoffVariable_polarfield = device_property(
        dtype='str', default_value='MAIN.AnalogIn6',
        doc="PLC LREAL variable for polar Hall-probe ADC input"
    )
    BeckhoffVariable_longitudinalfield = device_property(
        dtype='str', default_value='MAIN.AnalogIn5',
        doc="PLC LREAL variable for longitudinal Hall-probe ADC input"
    )
    HallSensitivity_polar = device_property(
        dtype=float, default_value=5.0,
        doc="Hall probe sensitivity for polar geometry [V/T]"
    )
    HallSensitivity_longitudinal = device_property(
        dtype=float, default_value=5.0,
        doc="Hall probe sensitivity for longitudinal geometry [V/T]"
    )

    def init_device(self):
        Device.init_device(self)
        self._current_polar = 0.0
        self._current_longitudinal = 0.0
        self._field_polar = 0.0
        self._field_longitudinal = 0.0
        self._corr_polar = 1.0
        self._corr_longitudinal = 1.0
        self.ads = tango.DeviceProxy(self.AdsBridge)
        self.info_stream("Magnet: using AdsBridge at " + self.AdsBridge)
        self.set_state(DevState.ON)
        self.set_status("Ready — AdsBridge: " + self.AdsBridge)

    def always_executed_hook(self):
        pass

    # ---- Attributes: current (RW) ---------------------------------------

    @attribute(dtype=float, access=AttrWriteType.READ_WRITE,
               unit='A', doc="Current through polar coil in Ampere")
    def current_polar(self):
        raw = self.ads.ReadReal(self.BeckhoffVariable_polar)
        self._current_polar = raw * self.AmperePerVolt_polar
        return self._current_polar

    @current_polar.write
    def current_polar(self, value):
        volts = value / self.AmperePerVolt_polar
        self._check_output_range(volts, value, self.AmperePerVolt_polar,
                                 "current_polar")
        self.ads.WriteReal("{}={:.6f}".format(self.BeckhoffVariable_polar, volts))

    @attribute(dtype=float, access=AttrWriteType.READ_WRITE,
               unit='A', doc="Current through longitudinal coil in Ampere")
    def current_longitudinal(self):
        raw = self.ads.ReadReal(self.BeckhoffVariable_longitudinal)
        self._current_longitudinal = raw * self.AmperePerVolt_longitudinal
        return self._current_longitudinal

    @current_longitudinal.write
    def current_longitudinal(self, value):
        volts = value / self.AmperePerVolt_longitudinal
        self._check_output_range(volts, value, self.AmperePerVolt_longitudinal,
                                 "current_longitudinal")
        self.ads.WriteReal("{}={:.6f}".format(self.BeckhoffVariable_longitudinal, volts))

    @staticmethod
    def _check_output_range(volts, amps, ampere_per_volt, attr_name):
        """The attribute sets a CURRENT in A; the PLC variable carries the
        converted programming voltage for the ±10 V DAC output that drives
        the supply.  Currents beyond 10 V x AmperePerVolt are physically
        unreachable — reject (not clamp) them so the user knows the setpoint
        was not honored.  The limit is reported in Ampere."""
        if abs(volts) > DAC_LIMIT_V:
            limit_a = DAC_LIMIT_V * abs(ampere_per_volt)
            tango.Except.throw_exception(
                "Current setpoint not reachable",
                "{} = {:.4g} A is outside the reachable range of "
                "±{:.4g} A for this coil "
                "(±{:.0f} V DAC output × AmperePerVolt = "
                "{:.4g} A/V) — check the value and the AmperePerVolt "
                "calibration property".format(
                    attr_name, amps, limit_a, DAC_LIMIT_V, ampere_per_volt),
                "Magnet::" + attr_name)

    # ---- Attributes: field (R) ------------------------------------------

    @attribute(dtype=float, unit='mT',
               doc="Magnetic field measured by polar Hall probe in mT")
    def field_polar(self):
        raw = self.ads.ReadReal(self.BeckhoffVariable_polarfield)
        self._field_polar = raw / self.HallSensitivity_polar * 1000.0
        return self._field_polar

    @attribute(dtype=float, unit='mT',
               doc="Magnetic field measured by longitudinal Hall probe in mT")
    def field_longitudinal(self):
        raw = self.ads.ReadReal(self.BeckhoffVariable_longitudinalfield)
        self._field_longitudinal = raw / self.HallSensitivity_longitudinal * 1000.0
        return self._field_longitudinal

    # ---- Attributes: corrected field (R) --------------------------------

    @attribute(dtype=float, unit='mT',
               doc="Polar field multiplied by correction factor corr_polar")
    def field_polar_corr(self):
        # Always do a fresh read so this attribute is independent of field_polar poll order
        raw = self.ads.ReadReal(self.BeckhoffVariable_polarfield)
        self._field_polar = raw / self.HallSensitivity_polar * 1000.0
        return self._field_polar * self._corr_polar

    @attribute(dtype=float, unit='mT',
               doc="Longitudinal field multiplied by correction factor corr_longitudinal")
    def field_longitudinal_corr(self):
        raw = self.ads.ReadReal(self.BeckhoffVariable_longitudinalfield)
        self._field_longitudinal = raw / self.HallSensitivity_longitudinal * 1000.0
        return self._field_longitudinal * self._corr_longitudinal

    # ---- Attributes: correction factors (RW) ----------------------------

    @attribute(dtype=float, access=AttrWriteType.READ_WRITE,
               memorized=True, hw_memorized=True,
               doc="Multiplicative correction factor for polar Hall probe reading")
    def corr_polar(self):
        return self._corr_polar

    @corr_polar.write
    def corr_polar(self, value):
        self._corr_polar = value

    @attribute(dtype=float, access=AttrWriteType.READ_WRITE,
               memorized=True, hw_memorized=True,
               doc="Multiplicative correction factor for longitudinal Hall probe reading")
    def corr_longitudinal(self):
        return self._corr_longitudinal

    @corr_longitudinal.write
    def corr_longitudinal(self, value):
        self._corr_longitudinal = value

    # ---- Commands -------------------------------------------------------

    @command()
    def SetZero_polar(self):
        """Set the polar coil current to zero."""
        self.ads.WriteReal(self.BeckhoffVariable_polar + '=0.0')
        self._current_polar = 0.0

    @command()
    def SetZero_longitudinal(self):
        """Set the longitudinal coil current to zero."""
        self.ads.WriteReal(self.BeckhoffVariable_longitudinal + '=0.0')
        self._current_longitudinal = 0.0


def main(args=None, **kwargs):
    return run((Magnet,), args=args, **kwargs)


if __name__ == '__main__':
    main()
