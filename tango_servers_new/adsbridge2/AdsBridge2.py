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

    # ---------------
    # General methods
    # ---------------

    def init_device(self):
        """Initializes the attributes and properties of the AdsBridge2."""
        Device.init_device(self)
        # PROTECTED REGION ID(AdsBridge2.init_device) ENABLED START #
        try:
            pyads.add_route(self.PlcAmsAddress, self.PlcIP)
            #self.plc = pyads.Connection(self.PlcAmsAddress, 851)
            self.plc = pyads.Connection(self.PlcAmsAddress, self.Port)
            self.plc.open()
        except Exception as e:
            self.set_state(PyTango.DevState.FAULT)
            PyTango.Except.throw_exception("Unable to kinit ADS bridge",
                str(e),
                "AdsBridge2::init_device")
        self.set_state(PyTango.DevState.ON)
        self.lock = threading.Lock()
        # PROTECTED REGION END #    //  AdsBridge2.init_device

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
        self.plc.close()
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
                self.plc.close()
                self.plc.open()
            self.set_state(PyTango.DevState.ON)
            self.set_status("Reconnected")
        except Exception as e:
            self.set_state(PyTango.DevState.FAULT)
            self.set_status("Reconnect failed: {}".format(e))
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
            with self.lock:
                return self.plc.read_by_name(argin, pyads.PLCTYPE_BOOL)
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
            with self.lock:
                self.plc.write_by_name(strings[0], arg, pyads.PLCTYPE_BOOL)
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
            with self.lock:
                return self.plc.read_by_name(argin, pyads.PLCTYPE_DINT)
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
            with self.lock:
                self.plc.write_by_name(strings[0], arg, pyads.PLCTYPE_DINT)
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
            with self.lock:
                return self.plc.read_by_name(argin, pyads.PLCTYPE_LREAL)
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
            with self.lock:
                self.plc.write_by_name(strings[0], arg, pyads.PLCTYPE_LREAL)
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
            with self.lock:
                return self.plc.read_by_name(argin, pyads.PLCTYPE_INT)
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
            with self.lock:
                self.plc.write_by_name(strings[0], arg, pyads.PLCTYPE_INT)
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

            with self.lock:
                # pyads syntax for reading arrays: Type * Count
                return self.plc.read_by_name(var_name, pyads.PLCTYPE_LREAL * count)
                
        except Exception as e:
            self.set_state(PyTango.DevState.FAULT)
            self.set_status(f"ADS error: ReadRealArray failed for {argin}. {str(e)}")
            # Return fallback list of -10.0 as per C++ implementation
            return [-10.0] * (count if 'count' in locals() else 1)
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

            with self.lock:
                # pyads syntax for reading arrays of DINT (32-bit int)
                return self.plc.read_by_name(var_name, pyads.PLCTYPE_DINT * count)

        except Exception as e:
            self.set_state(PyTango.DevState.FAULT)
            self.set_status(f"ADS error: ReadLongIntArray failed for {argin}. {str(e)}")
            # Return fallback list of -10 as per C++ implementation
            return [-10] * (count if 'count' in locals() else 1)
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
