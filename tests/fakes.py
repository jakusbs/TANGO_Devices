"""In-process fakes for the device servers' dependencies.

`FakeAdsBridge` stands in for AdsBridge2: the same command set the remade
servers call (`ReadBool`, `WriteBool("VAR=true")`, `ReadReal`, `WriteReal`,
`ReadShort`, `WriteShort`) over an in-memory symbol table.  `Trace` lists
every write in order, `FailWrites`/`FailReads` emulate a dead ADS link.
"""
import threading

import tango
from tango import DevState
from tango.server import Device, command


class FakeAdsBridge(Device):

    def init_device(self):
        super().init_device()
        self._vars = {}
        self._trace = []
        self._fail_w = False
        self._fail_r = False
        self._lock = threading.Lock()
        self.set_state(DevState.ON)

    def _check(self, write: bool):
        if (self._fail_w if write else self._fail_r):
            tango.Except.throw_exception(
                "ADS_link_down", "simulated ADS failure", "FakeAdsBridge")

    def _parse(self, arg: str):
        name, _, val = arg.partition("=")
        return name.strip(), val.strip()

    # ---- reads ----------------------------------------------------------
    @command(dtype_in=str, dtype_out=bool)
    def ReadBool(self, name):
        self._check(False)
        with self._lock:
            return bool(self._vars.get(name, False))

    @command(dtype_in=str, dtype_out=float)
    def ReadReal(self, name):
        self._check(False)
        with self._lock:
            return float(self._vars.get(name, 0.0))

    @command(dtype_in=str, dtype_out=int)
    def ReadShort(self, name):
        self._check(False)
        with self._lock:
            return int(self._vars.get(name, 0))

    # ---- writes ---------------------------------------------------------
    @command(dtype_in=str)
    def WriteBool(self, arg):
        self._check(True)
        name, val = self._parse(arg)
        with self._lock:
            self._vars[name] = val.lower() in ("true", "1")
            self._trace.append(f"{name}={str(self._vars[name]).lower()}")

    @command(dtype_in=str)
    def WriteReal(self, arg):
        self._check(True)
        name, val = self._parse(arg)
        with self._lock:
            self._vars[name] = float(val)
            self._trace.append(f"{name}={self._vars[name]}")

    @command(dtype_in=str)
    def WriteShort(self, arg):
        self._check(True)
        name, val = self._parse(arg)
        with self._lock:
            self._vars[name] = int(val)
            self._trace.append(f"{name}={self._vars[name]}")

    # ---- test controls --------------------------------------------------
    @command(dtype_out=(str,))
    def Trace(self):
        with self._lock:
            return list(self._trace)

    @command
    def ClearTrace(self):
        with self._lock:
            self._trace.clear()

    @command(dtype_in=bool)
    def FailWrites(self, flag):
        self._fail_w = bool(flag)

    @command(dtype_in=bool)
    def FailReads(self, flag):
        self._fail_r = bool(flag)
