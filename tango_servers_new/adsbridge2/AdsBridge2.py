# -*- coding: utf-8 -*-
#
# This file is part of the AdsBridge2 project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

"""
AdsBridge Version 2

ADS bridge version 2, using the pure Python
implementation of the bridge. It is compatible to the old AdsBridge
"""

# PROTECTED REGION ID(AdsBridge2.system_imports) ENABLED START #
# PROTECTED REGION END #    //  AdsBridge2.system_imports

# PyTango imports
import tango
from tango import DebugIt
from tango.server import run
from tango.server import Device
from tango.server import command
from tango.server import device_property
from tango import AttrQuality, DispLevel, DevState
from tango import AttrWriteType
# Additional import
# PROTECTED REGION ID(AdsBridge2.additionnal_import) ENABLED START #
import pyads
import threading
import time
import PyTango
# PROTECTED REGION END #    //  AdsBridge2.additionnal_import

__all__ = ["AdsBridge2", "main"]


class AdsBridge2(Device):
    """
    ADS bridge version 2, using the pure Python
    implementation of the bridge. It is compatible to the old AdsBridge

    **Properties:**

    - Device Property
        PlcAmsAddress
            - AMS address of the PLC
            - Type:'str'
        PlcIP
            - Type:'str'
        Port
            - ADS Port
            - Type:'int'
    """
    # PROTECTED REGION ID(AdsBridge2.class_variable) ENABLED START #
    # PROTECTED REGION END #    //  AdsBridge2.class_variable

    # -----------------
    # Device Properties
    # -----------------

    PlcAmsAddress = device_property(
        dtype='str',
        doc="AMS address of the PLC",
        mandatory=True
    )

    PlcIP = device_property(
        dtype='str',
        mandatory=True
    )

    Port = device_property(
        dtype='int',
        default_value=801,
        doc="ADS Port"
    )

    AutoReconnect = device_property(
        dtype=bool,
        default_value=True,
        doc="Rebuild the ADS connection automatically: a failed command "
            "reconnects and retries once before raising, and the keepalive "
            "watchdog repairs a dead link between commands."
    )

    KeepaliveInterval = device_property(
        dtype=float,
        default_value=10.0,
        doc="Seconds between watchdog keepalive reads (ADS ReadState). "
            "Keeps the connection non-idle (defeats idle-session timeouts "
            "in network gear / the PLC router) and detects a dead link "
            "between commands. 0 disables the watchdog thread."
    )

    # ---------------
    # General methods
    # ---------------

    def init_device(self):
        """Initializes the attributes and properties of the AdsBridge2."""
        Device.init_device(self)
        # PROTECTED REGION ID(AdsBridge2.init_device) ENABLED START #
        # lock/plc must exist before the connection attempt: a failed init
        # would otherwise leave them unset, and every later command —
        # including Reconnect, the designated recovery path — would die
        # with AttributeError instead of a clean DevFailed.
        self.lock = threading.Lock()
        self.plc = None
        self._reconnects = 0     # auto/manual reconnects since server start
        self._hb_fresh_fails = 0 # consecutive keepalive failures on a fresh connection
        self._wd_stop = threading.Event()
        self._wd_thread = None
        try:
            with self.lock:
                self._open_plc_locked()
        except Exception as e:
            # Do NOT throw: the watchdog / on-demand reconnect keep
            # retrying, so a PLC that is down at server start is picked
            # up automatically once it comes back.
            self.set_state(PyTango.DevState.FAULT)
            self.set_status("ADS connection failed at init: {}".format(e))
        else:
            self.set_state(PyTango.DevState.ON)
        if self.KeepaliveInterval > 0:
            self._wd_thread = threading.Thread(
                target=self._watchdog, name="AdsBridge2-watchdog", daemon=True)
            self._wd_thread.start()
        # PROTECTED REGION END #    //  AdsBridge2.init_device

    # ------------------------------------------------------------------
    # Connection management (auto-reconnect + keepalive watchdog)
    # ------------------------------------------------------------------

    # ADS error codes that are caller mistakes, not a dead link — never
    # worth a reconnect+retry (1808 = symbol not found, e.g. writing
    # HystSource1..6 to a PLC program that predates them).
    _NO_RETRY_ADS_CODES = {1808}

    def _open_plc_locked(self):
        """(Re)build and open the ADS connection. Caller holds self.lock."""
        if self.plc is not None:
            try:
                self.plc.close()
            except Exception:
                pass
            self.plc = None
        pyads.add_route(self.PlcAmsAddress, self.PlcIP)
        plc = pyads.Connection(self.PlcAmsAddress, self.Port)
        plc.open()
        self.plc = plc

    def _reconnect_locked(self, reason=""):
        """Rebuild the connection (caller holds self.lock). Raises on failure."""
        try:
            self._open_plc_locked()
        except Exception as e:
            self.set_state(PyTango.DevState.FAULT)
            self.set_status("ADS reconnect failed at {} ({}); retrying — "
                            "trigger was: {}".format(
                                time.strftime("%H:%M:%S"), e, reason))
            raise
        self._reconnects += 1
        self.set_state(PyTango.DevState.ON)
        self.set_status("ADS reconnect #{} at {} — trigger: {}".format(
            self._reconnects, time.strftime("%H:%M:%S"), reason))

    def _ads_call(self, op):
        """Run one ADS operation under the lock.

        On failure the connection is rebuilt and the operation retried
        once before the error propagates, so a link that died since the
        last command costs one hiccup instead of a failed read (and a
        '-----' panel) until someone runs Reconnect by hand.
        """
        with self.lock:
            try:
                return op()
            except Exception as e:
                if (not self.AutoReconnect
                        or getattr(e, 'err_code', None) in self._NO_RETRY_ADS_CODES):
                    raise
                self._reconnect_locked(reason="command error: {}".format(e))
                return op()

    def _watchdog(self):
        """Keepalive loop (daemon thread).

        A lightweight ADS ReadState every KeepaliveInterval seconds keeps
        the connection non-idle and repairs a dead link between commands.
        The non-blocking acquire means the watchdog never delays a real
        command: if the lock is busy, traffic is flowing and no keepalive
        is needed anyway.
        """
        try:
            guard = tango.EnsureOmniThread()
        except AttributeError:  # pytango < 9.3.2
            import contextlib
            guard = contextlib.nullcontext()
        with guard:
            interval = max(1.0, float(self.KeepaliveInterval))
            while not self._wd_stop.wait(interval):
                if not self.lock.acquire(blocking=False):
                    continue
                try:
                    self._keepalive_locked()
                finally:
                    self.lock.release()

    def _keepalive_locked(self):
        try:
            if self.plc is None:
                raise RuntimeError("no ADS connection")
            self.plc.read_state()
        except Exception as e:
            if not self.AutoReconnect:
                self.set_state(PyTango.DevState.FAULT)
                self.set_status("ADS keepalive failed: {}".format(e))
                return
            try:
                self._reconnect_locked(reason="keepalive: {}".format(e))
            except Exception:
                return  # FAULT + status already set; retry next cycle
            try:
                self.plc.read_state()
                self._hb_fresh_fails = 0
            except Exception as e2:
                # ReadState failing right after a successful reconnect —
                # after 3 in a row assume ReadState itself is the problem
                # (quirky target) and stop churning connections. The
                # on-demand reconnect in _ads_call still protects commands.
                self._hb_fresh_fails += 1
                if self._hb_fresh_fails >= 3:
                    self.warn_stream(
                        "keepalive ReadState keeps failing on fresh "
                        "connections ({}) — watchdog disabled, on-demand "
                        "reconnect remains active".format(e2))
                    self._wd_stop.set()
        else:
            self._hb_fresh_fails = 0
            if self.get_state() == PyTango.DevState.FAULT:
                self.set_state(PyTango.DevState.ON)
                self.set_status("ADS connection healthy again at {}".format(
                    time.strftime("%H:%M:%S")))

    def always_executed_hook(self):
        """Method always executed before any TANGO command is executed."""
        # PROTECTED REGION ID(AdsBridge2.always_executed_hook) ENABLED START #
        pass
        # PROTECTED REGION END #    //  AdsBridge2.always_executed_hook

    def delete_device(self):
        """Hook to delete resources allocated in init_device.

        This method allows for any memory or other resources allocated in the
        init_device method to be released.  This method is called by the device
        destructor and by the device Init command.
        """
        # PROTECTED REGION ID(AdsBridge2.delete_device) ENABLED START #
        if getattr(self, '_wd_stop', None) is not None:
            self._wd_stop.set()
        wd = getattr(self, '_wd_thread', None)
        if wd is not None and wd.is_alive():
            wd.join(timeout=2.0)
        if getattr(self, 'plc', None) is not None:
            try:
                self.plc.close()
            except Exception:
                pass
        # PROTECTED REGION END #    //  AdsBridge2.delete_device

    # --------
    # Commands
    # --------

    @command()
    @DebugIt()
    def Reconnect(self):
        # PROTECTED REGION ID(AdsBridge2.Reconnect) ENABLED START #
        """Close and reopen the ADS connection. Use after a PLC reboot or network fault."""
        try:
            with self.lock:
                self._reconnect_locked(reason="manual Reconnect command")
        except Exception as e:
            PyTango.Except.throw_exception("Reconnect failed", str(e), "AdsBridge2::Reconnect")
        # PROTECTED REGION END #    //  AdsBridge2.Reconnect

    @command(
        dtype_in='DevString',
        doc_in="Request",
        dtype_out='DevBoolean',
        doc_out="Response",
    )
    @DebugIt()
    def ReadBool(self, argin):
        # PROTECTED REGION ID(AdsBridge2.ReadBool) ENABLED START #
        try:
            return self._ads_call(
                lambda: self.plc.read_by_name(argin, pyads.PLCTYPE_BOOL))
        except Exception as e:
            PyTango.Except.throw_exception("Unable to read bool",
                str(e),
                "AdsBridge2::ReadBool")
        # PROTECTED REGION END #    //  AdsBridge2.ReadBool

    @command(
        dtype_in='DevString',
        doc_in="Request",
    )
    @DebugIt()
    def WriteBool(self, argin):
        # PROTECTED REGION ID(AdsBridge2.WriteBool) ENABLED START #
        
        strings = argin.split('=')
        arg = False
        if strings[1] == 'true':
            arg = True;
        else:
            if strings[1] == 'false':
                arg = False;
            else:
                PyTango.Except.throw_exception("Wrong argument, must be true or false",
                "Wrong argument, must be true or false",
                "AdsBridge2::WriteBool")
        
        try:
            self._ads_call(
                lambda: self.plc.write_by_name(strings[0], arg, pyads.PLCTYPE_BOOL))
        except Exception as e:
            PyTango.Except.throw_exception("Unable to set bool",
                str(e),
                "AdsBridge2::WriteBool")
        
        # PROTECTED REGION END #    //  AdsBridge2.WriteBool

    @command(
        dtype_in='DevString',
        doc_in="variable name",
        dtype_out='DevLong',
        doc_out="value",
    )
    @DebugIt()
    def ReadInt(self, argin):
        # PROTECTED REGION ID(AdsBridge2.ReadInt) ENABLED START #
        try:
            return self._ads_call(
                lambda: self.plc.read_by_name(argin, pyads.PLCTYPE_DINT))
        except Exception as e:
            PyTango.Except.throw_exception("Unable to read int",
                str(e),
                "AdsBridge2::ReadInt")
        # PROTECTED REGION END #    //  AdsBridge2.ReadInt

    @command(
        dtype_in='DevString',
        doc_in="variable=value",
    )
    @DebugIt()
    def WriteInt(self, argin):
        # PROTECTED REGION ID(AdsBridge2.WriteInt) ENABLED START #
        try:
            strings = argin.split('=')
            arg = int(strings[1])
            self._ads_call(
                lambda: self.plc.write_by_name(strings[0], arg, pyads.PLCTYPE_DINT))
        except Exception as e:
            PyTango.Except.throw_exception("Unable to write int",
                str(e),
                "AdsBridge2::WriteInt")    
        # PROTECTED REGION END #    //  AdsBridge2.WriteInt

    @command(
        dtype_in='DevString',
        doc_in="variable name",
        dtype_out='DevDouble',
        doc_out="value",
    )
    @DebugIt()
    def ReadReal(self, argin):
        # PROTECTED REGION ID(AdsBridge2.ReadReal) ENABLED START #
        try:
            return self._ads_call(
                lambda: self.plc.read_by_name(argin, pyads.PLCTYPE_LREAL))
        except Exception as e:
            PyTango.Except.throw_exception("Unable to read lreal",
                str(e),
                "AdsBridge2::ReadReal")
        # PROTECTED REGION END #    //  AdsBridge2.ReadReal

    @command(
        dtype_in='DevString',
        doc_in="variable=value",
    )
    @DebugIt()
    def WriteReal(self, argin):
        # PROTECTED REGION ID(AdsBridge2.WriteReal) ENABLED START #
        try:
            strings = argin.split('=')
            arg = float(strings[1])
            self._ads_call(
                lambda: self.plc.write_by_name(strings[0], arg, pyads.PLCTYPE_LREAL))
        except Exception as e:
            PyTango.Except.throw_exception("Unable to write lreal",
                str(e),
                "AdsBridge2::WriteReal") 
        # PROTECTED REGION END #    //  AdsBridge2.WriteReal

    @command(
        dtype_in='DevString',
        doc_in="variable name",
        dtype_out='DevLong',
        doc_out="value",
    )
    @DebugIt()
    def ReadShort(self, argin):
        # PROTECTED REGION ID(AdsBridge2.ReadShort) ENABLED START #
        try:
            return self._ads_call(
                lambda: self.plc.read_by_name(argin, pyads.PLCTYPE_INT))
        except Exception as e:
            PyTango.Except.throw_exception("Unable to read short",
                str(e),
                "AdsBridge2::ReadShort")
        # PROTECTED REGION END #    //  AdsBridge2.ReadShort

    @command(
        dtype_in='DevString',
        doc_in="variable=value",
    )
    @DebugIt()
    def WriteShort(self, argin):
        # PROTECTED REGION ID(AdsBridge2.WriteShort) ENABLED START #
        try:
            strings = argin.split('=')
            arg = int(strings[1])
            self._ads_call(
                lambda: self.plc.write_by_name(strings[0], arg, pyads.PLCTYPE_INT))
        except Exception as e:
            PyTango.Except.throw_exception("Unable to write short",
                str(e),
                "AdsBridge2::WriteShort")    
        # PROTECTED REGION END #    //  AdsBridge2.WriteShort


    @command(
        dtype_in='DevString',
        doc_in="Variable name, number of elements",
        dtype_out='DevVarDoubleArray',
        doc_out="array values",
    )
    @DebugIt()
    def ReadRealArray(self, argin):
        # PROTECTED REGION ID(AdsBridge2.ReadRealArray) ENABLED START #
        """
        Translates C++ ReadRealArray. 
        Input format: "VariableName,Count"
        """
        try:
            # Parse input "name,count"
            parts = argin.split(',')
            var_name = parts[0].strip()
            count = int(parts[1].strip())
            
            if count < 1:
                count = 1

            # pyads syntax for reading arrays: Type * Count
            return self._ads_call(
                lambda: self.plc.read_by_name(var_name, pyads.PLCTYPE_LREAL * count))

        except Exception as e:
            # Throw like every other command — the old C++-style -10.0
            # filler handed the caller (PyHysteresis) plausible-looking
            # data with no error, and the FAULT it latched was never
            # cleared by later successful calls.
            PyTango.Except.throw_exception("Unable to read lreal array",
                "ReadRealArray failed for {}: {}".format(argin, e),
                "AdsBridge2::ReadRealArray")
        # PROTECTED REGION END #    //  AdsBridge2.ReadRealArray

    @command(
        dtype_in='DevString',
        doc_in="Variable name, number of elements",
        dtype_out='DevVarLongArray',
        doc_out="array values",
    )
    @DebugIt()
    def ReadLongIntArray(self, argin):
        # PROTECTED REGION ID(AdsBridge2.ReadLongIntArray) ENABLED START #
        """
        Translates C++ ReadLongIntArray.
        Input format: "VariableName,Count"
        """
        try:
            # Parse input "name,count"
            parts = argin.split(',')
            var_name = parts[0].strip()
            count = int(parts[1].strip())
            
            if count < 1:
                count = 1
                
            # C++ implementation capped this at 750
            if count > 750:
                count = 750

            # pyads syntax for reading arrays of DINT (32-bit int)
            return self._ads_call(
                lambda: self.plc.read_by_name(var_name, pyads.PLCTYPE_DINT * count))

        except Exception as e:
            # Throw like every other command (see ReadRealArray).
            PyTango.Except.throw_exception("Unable to read dint array",
                "ReadLongIntArray failed for {}: {}".format(argin, e),
                "AdsBridge2::ReadLongIntArray")
        # PROTECTED REGION END #    //  AdsBridge2.ReadLongIntArray



# ----------
# Run server
# ----------

# PROTECTED REGION ID(AdsBridge2.custom_code) ENABLED START #
# PROTECTED REGION END #    //  AdsBridge2.custom_code


def main(args=None, **kwargs):
    """Main function of the AdsBridge2 module."""
    # PROTECTED REGION ID(AdsBridge2.main) ENABLED START #
    return run((AdsBridge2,), args=args, **kwargs)
    # PROTECTED REGION END #    //  AdsBridge2.main

# PROTECTED REGION ID(AdsBridge2.custom_functions) ENABLED START #
# PROTECTED REGION END #    //  AdsBridge2.custom_functions


if __name__ == '__main__':
    main()
