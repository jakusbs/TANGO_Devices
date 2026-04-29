# TANGO Devices — Project Context

## Repository Structure

```
tango_servers_old/                  # Original C++ (and some old Python) servers — do not modify
tango_servers_old/software_windows/ # Windows-side software: Beckhoff TwinCAT programs,
                                    # AttoDRY socket bridge scripts, hardware manuals (PDFs)
tango_servers_new/                  # AdsBridge2 and ZI servers (newer Python, kept separately)
tango_servers_remade/               # All servers ported to modern Python 3 tango.server API
```

Install target for all servers: `/usr/local/tango_servers`

Each server in `tango_servers_remade/` has:
- `<Server>.py` — the implementation
- `<Server>.xmi` — POGO PogoDSL 9.1 (PythonHL) descriptor for documentation
- `install.sh` — prepends shebang, makes executable, installs to `/usr/local/tango_servers`

---

## Servers in tango_servers_remade/

| Server | Hardware | Notes |
|---|---|---|
| `Socket` | TCP gateway | Used by ANC300, PyKeithley, PyKeithley2, PyKeithleyPulse |
| `Magnet` | Magnet power supply | |
| `ANC300` | Attocube ANC300 piezo controller | via Socket proxy |
| `ANM200` | ANM200 nano-positioner | |
| `AttoDRY` | AttoDRY2100 cryostat | UDP, has daemon thread |
| `DoubleInBeckhoffAverage` | Beckhoff ADS double input with averaging | |
| `Lights` | LED light controller | |
| `PyKeithley` | Keithley 6221 unit 1 | via Socket; trigger line 5 |
| `PyKeithley2` | Keithley 6221 unit 2 | via Socket; trigger line 3 |
| `PyKeithleyPulse` | Keithley 6221 square-wave mode | via Socket; same hardware as PyKeithley |
| `PyRelais` | Relay controller | |

---

## Socket Server — Critical Notes

The Python Socket server must match the behaviour of the original C++ Socket server.
Key differences found by comparing C++ and Python:

### `Write` appends `\r\n` (not just `\n`)
The C++ `Write` command always appended `\r\n`. The Python `Write` command must do the same.
`WriteLine` appends only `\n`. `WriteRead` and `WriteReadUntil` also append `\r\n` (matching C++).

### Error handling — only disconnect on connection errors
The C++ server only marked the connection as broken on: `ECONNRESET`, `EPIPE`, `ENOTCONN`, `EINTR`.
Timeouts (`EAGAIN`, `ETIMEDOUT`) raised an exception but kept the connection alive.

The Python server uses `_handle_error()` which only calls `_on_socket_error()` (disconnect + reconnect)
for `BrokenPipeError`, `ConnectionResetError`, `ConnectionAbortedError`, `ConnectionRefusedError`.
Timeouts re-raise directly without disconnecting.

### AutoReconnect property (default True)
- On connection error: closes socket, sets FAULT, immediately attempts reconnect
- `_require_connected()`: if `_sock is None` and AutoReconnect, tries to reconnect before raising
- `Reconnect` command: catches all exceptions gracefully — sets FAULT with status message, does not raise (so caller can retry after ~60 seconds)

### Non-blocking socket (C++) vs blocking with timeout (Python)
The C++ socket was non-blocking (`set_non_blocking(true)`). The Python socket is blocking with
`Readtimeout` ms timeout (default 1000 ms). Functionally equivalent for the use cases here.

---

## Keithley 6221 — Known Issues and Fixes

### Hardware
- **Unit 1 (PyKeithley)**: firmware D02 — has TCP drop bug, drops connection silently
- **Unit 2 (PyKeithley2)**: firmware D04 — stable, but affected by same Socket issues
- D04 firmware update available at: `https://www.tek.com/en/support/software/firmware/62206221-firmware-revision-d04`
- D04 has no USB port — firmware update must be done via RS-232 or GPIB
- **Do NOT install E-series firmware on D-series hardware** (bricks the unit)

### TCP connection behaviour (from Keithley 6221 manual 622x-901-01)
- Port: **1394** (raw TCP, not standard SCPI port 5025)
- Only **one TCP client at a time** — if previous session was not cleanly closed, new connection is blocked for ~30–60 seconds (TCP TIME_WAIT)
- When TCP drops, instrument **keeps running** (waveform continues, output stays on)
- Reconnecting to an instrument mid-wave: must send `SOUR:WAVE:ABOR` before any config commands

### SCPI commands — important rules
- All commands need `\n` terminator — use `WriteLine` not `Write`
- Waveform state machine: IDLE → `SOUR:WAVE:ARM` → ARMED → `SOUR:WAVE:INIT` → RUNNING
- Cannot write any `SOUR:WAVE:*` parameter while ARMED or RUNNING — causes settings-conflict error
- Always send `SOUR:WAVE:ABOR` before reconfiguring (safe to call in IDLE — no-op)
- Empirical: 100 ms delay required between last config command and `SOUR:WAVE:ARM`

### Fixes applied to PyKeithley, PyKeithley2, PyKeithleyPulse
1. All commands use `WriteLine` (adds `\n` terminator)
2. `SOUR:WAVE:ABOR` sent at start of `SINEWAVE`/`SQUAREWAVE`/`_rearm()` to ensure IDLE state
3. Recovery sequence in `init_device()`: `SOUR:WAVE:ABOR` + `OUTP OFF` (wrapped in try/except — instrument may not be ready immediately)
4. 100 ms `time.sleep(0.1)` before `SOUR:WAVE:ARM` in all waveform commands
5. PyKeithleyPulse: `_wave_running` flag — writing any parameter while wave is running auto-rearms the wave (no manual WAVEOFF/SQUAREWAVE cycle needed)
6. PyKeithleyPulse: `range` attribute added (same strings as PyKeithley/PyKeithley2)
7. PyKeithleyPulse: `pulseDuration` is a **computed** attribute (not stored independently) — reads as `1 / (2 × frequency)`, writes update `frequency` via `frequency = 1 / (2 × duration)`. Changing either `frequency` or `pulseDuration` updates the other automatically. Writing ≤ 0 raises `DevFailed`. Not memorized (derived value).

### PyKeithleyPulse range map
```python
'0.0002mA': '2e-7', '0.002mA': '2e-6', '0.02mA': '2e-5',
'0.2mA': '2e-4', '2mA': '0.002', '20mA': '0.02', '100mA': '0.1'
```
Note: PyKeithley/PyKeithley2 use different (older) range values inherited from old code —
do not change those without verifying on the actual hardware.

---

## AttoDRY — Notes

- Connects via UDP (not TCP) to a Windows PC running AttoDRY2100 software
- Properties: `AttoIP` (Windows PC IP), `AttoPort` (UDP port on PC), `LocalIP` (local NIC to bind to), `LocalPort` (local UDP port)
- `LocalIP` default is `0.0.0.0` (bind all interfaces) — works on any machine without updating the database. `LocalPort` default is `11005`.
- The `install.sh` copies three files: `AttoDRY` (executable), `AttoDRYThreadDaemon.py`, `AttoDRYCheck.py`

### Two-thread architecture
The remade AttoDRY uses two threads that must coexist cleanly:

1. **`AttoDRYThread`** (daemon, `AttoDRYThreadDaemon.py`) — runs continuously; sends `"Read"` every 0.2 s and parses the `ReadA...N` UDP packet to update all attribute caches. Started once by `Start()` and never restarted unless it dies.

2. **`AttoDRYCheck`** (`AttoDRYCheck.py`) — short-lived; started each time a `MagneticField` or `Temperature` setpoint is written. Polls the cached values (kept fresh by the daemon) and holds device state at `MOVING` until both field and temperature are within tolerance (0.001 T, 0.2 K), then sets state to `ON`. Without this thread there is no `MOVING` feedback — the device would appear done immediately after writing a setpoint.

### AttoDRYCheck — stop/restart on new setpoint
When a new setpoint arrives while `AttoDRYCheck` is still running (previous setpoint not yet reached):
- `stop()` sets `_stop_event` which immediately wakes the sleeping thread and exits its loop
- `join(timeout=1.0)` in `write_MagneticField`/`write_Temperature` waits for the old thread to finish before starting the new one — avoids two check threads running simultaneously against the same targets

`stop()` must set the event and nothing else. Do **not** call `set_state()` inside `stop()` — the new thread will own the state from the moment it starts.

### Attribute cache thread safety
`AttoDRY.init_device()` creates `self._cache_lock` (a `threading.Lock`).
`AttoDRYThread` holds this lock while writing all 26 attribute cache fields in one block.
`AttoDRYCheck` reads field/temperature caches under the same lock.
The main TANGO thread reads attributes directly from the cache (no lock needed for individual float reads on CPython, but the lock prevents partial-packet snapshots).

### Socket timeout
`Connect()` sets `s.settimeout(5.0)` before the handshake `recvfrom()`. If the Windows PC does not respond within 5 s the device goes to `OFF` cleanly instead of blocking forever. The daemon thread's `recvfrom()` also benefits — it catches `socket.timeout` and simply sleeps for the poll interval before retrying.

### Connect() port collision fix
`Connect()` stops the daemon listener and closes the existing socket **before** rebinding the port. Without this, calling `Connect()` a second time (e.g. manually from Jive) while the daemon was already running raised `OSError: Address already in use`. Sequence:
1. `listener.stop()` + `listener.join(timeout=2.0)` — daemon exits cleanly
2. `self.s.close()` — releases the port
3. New socket created, bound, timeout set, handshake performed

### AttoSocket2.py (Windows bridge, tango_servers_old/software_windows/)
Windows-side UDP bridge between the TANGO AttoDRY server and the PyAttoDRY DLL. Key design points:
- **Immediate ACK**: on `'start'` or `'ON'`, sends `b'ON'` reply *before* calling `connect_attodry()`. TANGO `Connect()` has a 5 s `recvfrom` timeout; the DLL init can take up to 10 s — without this the TANGO side always timed out and went to OFF.
- **Socket timeout**: `s.settimeout(10.0)` — no longer blocks forever if TANGO disappears.
- **Last-good-packet cache** (`last_packet`): if `build_packet()` fails or the DLL is not yet connected, the last successfully built `ReadA…N` packet is resent so the TANGO daemon does not stall on a missing reply.
- **Connection health check**: before each `Read`, calls `isDeviceConnected()` + `isDeviceInitialised()`; skips the DLL read and resends last packet if unhealthy.
- **All DLL calls wrapped in try/except** — a single failing DLL call does not crash the bridge.
- **No 10 ms inter-read sleeps** — DLL reads are from LabVIEW's cached state, so delays are unnecessary.
- Configuration constants at top of file: `HOST`, `PORT`, `COM_PORT`, `RECV_TIMEOUT_S`, `CONNECT_WAIT_S`.

### Known freeze points in the AttoDRY chain
Three identified freeze points:
1. **ACK timing** (fixed): AttoSocket2 must ACK before TANGO's 5 s timeout; DLL init is done in the background.
2. **Port collision** (fixed): TANGO `Connect()` now stops the daemon and closes the socket before rebinding.
3. **LabVIEW DLL deadlock** (unmitigatable in software): if `AttoDRYLib.dll` deadlocks internally, `build_packet()` or `connect_attodry()` will block forever. Only fix is restarting the Windows process. The bridge's socket timeout prevents the TANGO side from freezing in this case — TANGO sees repeated socket timeouts and stays in its last state.

---

## POGO / XMI Files

- All `.xmi` files use namespace `http://tango-controls.org/pogo/PogoDsl` (PythonHL, `pogoRevision="9.1"`)
- POGO can read these files and generate a skeleton, but the existing Python files are hand-written (no protected region markers) — POGO would overwrite them if code generation is run
- XMI files are kept for documentation and structural reference, not for active POGO code generation

### Memorized attribute mapping
- `memorized="true" memorizedAtInit="true"` → Python `memorized=True, hw_memorized=True`
- `memorized="true"` only → Python `memorized=True, hw_memorized=False`

---

## ANC300 — Notes

- Connects **directly via TCP** (Telnet, port **7230**) — no Socket proxy required
- Properties: `Hostname` (mandatory, IP of ANC300), `Port` (default 7230), `Readtimeout` (default 1000 ms), `password` (default `123456`), `addr_x/y/z` (axis addresses, defaults 4/5/6)
- On connect: discards Telnet IAC negotiation bytes (first recv), then sends password and checks for `'Authorization success'` in reply
- Commands use ASCII text with `\r\n` terminator — `_send()` appends this internally
- Command response timeout per manual: ~30 ms — the 100 ms sleeps in read helpers are safe
- `Reconnect` command: closes and reopens the socket; safe to call while other measurements are running (independent of Socket device)
- The old `Proxy` device property may still exist in the TANGO database — it is ignored by the new code

### Why direct TCP instead of Socket proxy
The Socket server is shared between Keithleys; restarting it while a measurement is running would
drop those connections. ANC300 has its own dedicated TCP connection, so it benefits from owning
the socket directly rather than going through an intermediary.

### Position writes (px/py/pz)
Position is tracked as a **relative step counter** — the hardware has no absolute encoder.
Write sequence: `setm <addr> stp` → sleep 0.1 s → `stepu`/`stepd`. Both commands must succeed before the cache is updated. If steps == 0 the step command is skipped (was previously issuing a `stepd 0`).

### Ground attributes (Gx/Gy/Gz)
- Write `True` → `setm <addr> gnd`
- Write `False` → `setm <addr> stp` (return to stepping mode)
- Previously, writing `False` was a silent no-op on hardware while updating the cache — fixed.

### Ground() command
Loops over all three axes with individual `try/except`; all axes are attempted even if one fails. Errors are collected and raised together at the end as a single `DevFailed`.

---

## ANM200 — Notes

- Controls three ANM200 DC piezo motors via three **DoubleOutBeckhoff** TANGO proxies
- Proxy chain: ANM200 → DoubleOutBeckhoff → AdsBridge2 → Beckhoff PLC
- Each proxy exposes a `Value` attribute (float, volts) that maps to one `AOC` output on the PLC
- Hardware limit: **±10 V** (Beckhoff AOC DAC range = ANM200 DC input range)

### Scaling
`scaling` converts between user units (µm) and DAC voltage: `voltage = position × scaling`.
- Default: `1.0` (1 V per unit). Must be set to the correct µm/V value before using position attributes.
- Writing `scaling = 0` raises `DevFailed` immediately.
- Writing a position that would require `abs(voltage) > 10 V` raises `DevFailed` before the hardware write.

### Startup state
`init_device()` reads the current `Value` from each DoubleOutBeckhoff proxy so the cached position reflects the actual hardware output. Without this, the cache starts at 0.0 V regardless of what the DAC was last set to.

---

## Beckhoff / DoubleInBeckhoffAverage — Notes

- `DoubleInBeckhoff` (in `tango_servers_new/PythonDoubleInBeckhoff/`) — simple live read of one PLC variable via AdsBridge2; no caching, no averaging.
- `DoubleInBeckhoffAverage` (in `tango_servers_remade/`) — adds on-board PLC averaging with `Start()`/`Abort()` commands and an `IntegrationTime` attribute.

### DoubleInBeckhoffAverage — key points
- `Start()` writes the averaging flag to the PLC **first**, then sets device state to `RUNNING`. (Previously state was set before the write — a failed write would leave the device stuck in RUNNING.)
- `Value` read raises on ADS failure (sets FAULT + logs) instead of silently returning −10.0.
- `IntegrationTime` is validated: must be > 0 and must not exceed **32.767 s** (32767 PLC cycles — the maximum for a 16-bit signed INT, which is what `AverageNum` is in the PLC).
- `always_executed_hook` surfaces ADS communication failures as FAULT state.

### Beckhoff TwinCAT program snapshots (software_windows/Beckhoff/)
Four versions of the PLC program are archived: Aug2020, Apr2023, Juni2024, Novi2025.
All run on a CX-16FC90, 1 ms task cycle, TwinCAT 2.11.

Key symbols accessible via ADS:
- `AnalogIn1_raw`–`AnalogIn6_raw` (DINT), `AnalogOut1_raw`–`AnalogOut4_raw` (INT)
- `AOC1`–`AOC8` (INT, 16-bit outputs → ANM200 channels), `ELM1`–`ELM6`
- `DigitalOut1`–`DigitalOut8` (BOOL)
- Averaging: `AverageNum`/`Averaging`/`AverageAbort` (three independent engines)
- Time-trace arrays `TT1`–`TT6`: fixed 400 points — cannot be resized without recompiling
- Hysteresis: `HystField`, `HystResult1`–`6`, `HystArrayLengthMax` (400 points)
- `HystFieldOffset` added in **Juni2024** — absent in Aug2020/Apr2023; reading it on older firmware raises an ADS symbol-not-found error
- Signal processing objects: `P_Lockin`, `P_PLL`, `P_Demod`, `P_FFTraw`, `P_SignalGenerator`

---

## AdsBridge2 — Notes

Lives in `tango_servers_new/adsbridge2/`. Replaces the old C++ AdsBridge. Uses `pyads` (pure Python ADS library).

- All read **and** write commands hold `self.lock` (a `threading.Lock`) — concurrent access is safe.
- `ReadBool` input: plain variable name (e.g. `MAIN.Averaging`)
- `WriteBool` input: `"VARIABLE=true"` or `"VARIABLE=false"` — note the asymmetry with ReadBool.
- `Reconnect` command: closes and reopens the ADS connection without restarting the server process. Use after a PLC reboot or network fault.
- No automatic reconnection — if the ADS connection drops for any reason other than calling `Reconnect`, all subsequent commands will throw exceptions until `Reconnect` is called.

---

## Other TANGO servers

### PyRelais
- ON/OFF commands use a ground → switch → unground sequence. The unground step is wrapped in `try/finally` so it still runs if the middle write fails, leaving the relay in a safe ungrounded state.
- Default Beckhoff variables use the `MAIN.` prefix (case-sensitive, matches the Beckhoff TwinCAT symbol table).

### Lights
- Default variables also use the `MAIN.` prefix.
- Read-modify-state sequence is non-atomic (write first, then read the other LED to set DevState). Concurrent calls can produce a state that disagrees with hardware — callers should serialise LED commands.

### PyHysteresis (in tango_servers_new/)
- `Abort()` guards with `hasattr` so it can be called safely before `Start()` without raising.
- `HysteresisThread` has a hard 600 s per half-loop timeout on the `HystRunning` PLC flag so a stuck flag cannot hang the thread forever — it auto-aborts on the PLC side and returns.
- `BeckhoffHystChannelValue` device property is **mandatory** in practice; comparing to `1` selects DAC1 (longitudinal), anything else falls to DAC2 (polar).

### Socket (remade)
- `Write` / `WriteRead` / `WriteReadUntil` / `WriteAndRead` all append `\r\n` (match original C++ Socket server).
- `WriteLine` appends only `\n` (for SCPI instruments like the Keithley).
- `Readln` strips a trailing `\r` before returning, so callers using `\r\n` protocols get a clean string.

### DG645 (in tango_servers_new/Digital_delay/)
- SRS DG645 Digital Delay Generator over TCP (default port 5025).
- Uses an `RLock` because `_reconnect` calls `_query` from inside a held lock.
- Rate-limited reconnect (`ReconnectInterval` class property, default 5 s) prevents reconnect storms.

### RTV40 (in tango_servers_new/RTV40_pulser/)
- Kentech RTV40 / RTV30 HV pulse generator over USB virtual COM port.
- Background poll thread owns all serial reads; attribute getters return cached values only, so TANGO polling cannot interleave with an active write.
- Wire-unit conversions: amplitude V → 0.1 V integer; pulse width ns → ps integer; clamping is applied before the wire write.

### SmarActMCS2Stage (in tango_servers_new/)
- Wraps three motor axis proxies. If any `DeviceProxy` fails in `init_device`, the corresponding `_x_proxy` / `_y_proxy` / `_z_proxy` stays `None`; attribute reads and `Stop()` now guard against this and raise a clear `DevFailed` instead of `AttributeError`.

### SetupLock (in tango_servers_new/)
- Three-way mutex device (green / IR / cryo setups). State flips to `RUNNING` when any `*Busy` flag is True, otherwise `ON`.

### DoubleInBeckhoff / DoubleOutBeckhoff (in tango_servers_new/)
- Minimal passthrough wrappers around AdsBridge2 `ReadReal` / `WriteReal`. No caching. No error handling — exceptions from AdsBridge propagate directly to the caller.

### ZI / ZI2 (in tango_servers_new/ZurichInstruments_lockin*_correct_read/)
- Both are Zurich Instruments MFLI lock-in servers. They differ only by default device ID (`dev4855` vs `dev30933`), default host IP and default `Harmonics`.
- **Ported to modern `tango.server.Device` API.** All ZI paths are now built from a `DeviceId` device property — no source edits needed to point at a different MFLI.
- New device properties: `DeviceId`, `ZI_Host`, `ZI_Port`, `ZI_ApiLevel`, `Harmonics` (4-element int array).
- `ZI2` defaults `Harmonics = [1,2,3,1]` — demod 3 uses harmonic 1 (not 4 as in `ZI`) per a 2024 change. Preserved as the property default; do not change without verifying the experimental setup.
- The companion `ThreadZI` / `ThreadZI2` no longer carry a hardcoded `DEVICE` constant — they pull `DeviceId` from the parent and write into `parent._x[i]` / `parent._y[i]`.
- Source files keep `from ThreadZI import ThreadZI` (resp. `ThreadZI2`); the `install_*_DAQ.sh` scripts rename `ThreadZI_DAQ.py` → `ThreadZI.py` and rewrite the import to a relative one inside the `ZI_DAQ` / `ZI2_DAQ` package. The launch entry point (`ZI_DAQ <instance>`) and Jive class names (`ZI`, `ZI2`) are unchanged.

---

## What Still Needs Attention

- **D02 firmware on Keithley unit 1**: The real fix is updating to D04. The AutoReconnect in Socket provides a software mitigation but the firmware drop is the root cause.
- **Network switch/router timeout**: Both Keithleys dropping connections suggests a network device may be killing idle TCP sessions. TCP keepalives (already attempted but reverted due to other bugs) or periodic heartbeat commands would help if confirmed.
- **AdsBridge2 auto-reconnect**: currently requires manual `Reconnect` command after PLC reboot. A watchdog that detects ADS errors and retries would be an improvement.
- **ANC300 position counter**: the `px/py/pz` attributes track a relative step counter that resets to 0 on server restart. There is no absolute position feedback — the counter drifts if steps are missed due to a communication error.
- **Magnet zero-guards**: `HallSensitivity_*` and `AmperePerVolt_*` are mandatory properties, but there is no runtime guard against a user setting them to 0 via Jive. Consider adding checks in `init_device`.
- **DG645 dev_state()**: polls `LERR?` on every state query, which can be frequent. If the state polling overhead becomes a problem, cache the last known state and only re-query after a timeout.
