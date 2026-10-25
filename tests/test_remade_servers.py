"""The remade device servers, served in-process by `tango.test_context`
against a fake AdsBridge2 — no database, no PLC, no hardware.

Run from the repo root:  python -m pytest tests -q
"""
import importlib.util
import os
import sys

import pytest

tango = pytest.importorskip("tango")
from tango import DevState                                      # noqa: E402
from tango.test_context import DeviceTestContext                # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from fakes import FakeAdsBridge                                 # noqa: E402


def _load(rel, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, rel))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


SetupLock = _load("tango_servers_new/SetupLock/SetupLock.py", "SetupLock").Setup_lock
PyRelais = _load("tango_servers_remade/PyRelais/PyRelais.py", "PyRelais").PyRelais
Averager = _load("tango_servers_remade/DoubleInBeckhoffAverage/DoubleInBeckhoffAverage.py",
                 "DoubleInBeckhoffAverage").DoubleInBeckhoffAverage


def _ctx(cls, **kw):
    try:
        ctx = DeviceTestContext(cls, process=True, timeout=30, **kw)
        p = ctx.__enter__()
    except Exception as e:                                      # pragma: no cover
        pytest.skip(f"cannot start an in-process device server here: {e}")
    return ctx, p


class _Ads:
    """The fake AdsBridge proxy plus its FULL access name.

    `proxy.name()` is the short nodb name; a server in another process
    resolves that against its own port.  The property handed to PyRelais /
    the averager must be the `tango://host:port/...#dbase=no` form.
    """
    def __init__(self, ctx, proxy):
        self.proxy, self.access = proxy, ctx.get_device_access()

    def __getattr__(self, item):
        return getattr(self.proxy, item)


@pytest.fixture(scope="module")
def ads():
    ctx, p = _ctx(FakeAdsBridge)
    try:
        yield _Ads(ctx, p)
    finally:
        ctx.__exit__(None, None, None)


# ── SetupLock ────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def lock():
    ctx, p = _ctx(SetupLock)
    try:
        yield p
    finally:
        ctx.__exit__(None, None, None)


def test_lock_busy_drives_state_and_clears_info(lock):
    assert lock.state() == DevState.ON
    lock.greeninfo = "pc1:1 @ 2026-10-24 10:00:00"
    lock.greenbusy = True
    assert lock.state() == DevState.RUNNING
    assert lock.greeninfo.startswith("pc1")
    lock.greenbusy = False
    assert lock.state() == DevState.ON
    assert lock.greeninfo == "", "releasing auto-clears the holder stamp"


def test_locks_are_independent(lock):
    lock.irbusy = True
    assert lock.state() == DevState.RUNNING
    assert not lock.greenbusy and not lock.cryobusy
    lock.irbusy = False


# ── PyRelais ─────────────────────────────────────────────────────────────────

@pytest.fixture
def relay(ads):
    ads.ClearTrace(); ads.FailWrites(False); ads.FailReads(False)
    ctx, p = _ctx(PyRelais, properties={"AdsBridge": ads.access,
                                        "BeckhoffVariable": "MAIN.DigitalOut2",
                                        "BeckhoffGround": "MAIN.DigitalOut7"})
    try:
        yield p
    finally:
        ctx.__exit__(None, None, None)


def test_relay_write_is_ground_switch_unground(relay, ads):
    relay.switchvar = 1
    assert list(ads.Trace()) == ["MAIN.DigitalOut7=true", "MAIN.DigitalOut2=true",
                                 "MAIN.DigitalOut7=false"]
    assert relay.state() == DevState.ON
    assert relay.switchvar == 1
    ads.ClearTrace()
    relay.switchvar = 0
    assert list(ads.Trace()) == ["MAIN.DigitalOut7=true", "MAIN.DigitalOut2=false",
                                 "MAIN.DigitalOut7=false"]
    assert relay.state() == DevState.STANDBY


def test_relay_actuates_on_every_write_even_unchanged(relay, ads):
    """Documented behaviour the SAMBA scanlist now avoids: writing the value
    the relay already has still runs the full switching sequence."""
    relay.switchvar = 1
    ads.ClearTrace()
    relay.switchvar = 1
    assert len(ads.Trace()) == 3


def test_failed_switch_still_ungrounds_and_raises(relay, ads):
    relay.switchvar = 1
    ads.ClearTrace()
    ads.FailWrites(True)
    with pytest.raises(tango.DevFailed):
        relay.switchvar = 0
    ads.FailWrites(False)
    # Cache only follows a successful switch.
    assert relay.switchvar == 1


# ── DoubleInBeckhoffAverage ──────────────────────────────────────────────────

@pytest.fixture
def avg(ads):
    ads.ClearTrace(); ads.FailWrites(False); ads.FailReads(False)
    ads.WriteBool("MAIN.Averaging=false")
    ctx, p = _ctx(Averager, properties={"AdsBridge": ads.access,
                                        "BeckhoffVariable": "MAIN.Avg1"})
    try:
        yield p
    finally:
        ctx.__exit__(None, None, None)


def test_integration_time_maps_to_plc_cycles(avg, ads):
    avg.IntegrationTime = 0.1
    assert ads.ReadShort("MAIN.AverageNum") == 100
    assert avg.IntegrationTime == pytest.approx(0.1)
    with pytest.raises(tango.DevFailed):
        avg.IntegrationTime = 40.0           # > 32767 PLC cycles
    with pytest.raises(tango.DevFailed):
        avg.IntegrationTime = 0.0


def test_start_runs_until_the_plc_clears_the_flag(avg, ads):
    avg.Start()
    assert ads.ReadBool("MAIN.Averaging") is True
    assert avg.state() == DevState.RUNNING
    ads.WriteBool("MAIN.Averaging=false")      # the PLC finishes
    assert avg.state() == DevState.ON
    ads.WriteReal("MAIN.Avg1=2.5")
    assert avg.Value == pytest.approx(2.5)


def test_failed_start_raises_and_leaves_the_device_on(avg, ads):
    """A PLC write failure in Start raises — with the state still ON, because
    the state change comes after the write.  The SAMBA engine learns of it
    only by collecting the asynchronous Start reply (Samba §86 D1)."""
    ads.FailWrites(True)
    with pytest.raises(tango.DevFailed):
        avg.Start()
    ads.FailWrites(False)
    assert avg.state() == DevState.ON
