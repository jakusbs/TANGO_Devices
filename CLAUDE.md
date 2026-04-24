# TANGO Devices — Project Context

## Repository Structure

```
tango_servers_old/      # Original C++ (and some old Python) servers — do not modify
tango_servers_new/      # AdsBridge2 and ZI servers (newer Python, kept separately)
tango_servers_remade/   # All servers ported to modern Python 3 tango.server API
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
5. PyKeithleyPulse: `_wave_running` flag — writing any parameter while wave is running auto-rearmsthe wave (no manual WAVEOFF/SQUAREWAVE cycle needed)
6. PyKeithleyPulse: `range` attribute added (same strings as PyKeithley/PyKeithley2)

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
- `LocalIP` and `LocalPort` were hardcoded in the old server (`192.168.1.7`, `11005`). They are now device properties with those same defaults — no database change needed for existing setups.
- The `install.sh` copies three files: `AttoDRY` (executable), `AttoDRYThreadDaemon.py`, `AttoDRYCheck.py`

---

## POGO / XMI Files

- All `.xmi` files use namespace `http://tango-controls.org/pogo/PogoDsl` (PythonHL, `pogoRevision="9.1"`)
- POGO can read these files and generate a skeleton, but the existing Python files are hand-written (no protected region markers) — POGO would overwrite them if code generation is run
- XMI files are kept for documentation and structural reference, not for active POGO code generation

### Memorized attribute mapping
- `memorized="true" memorizedAtInit="true"` → Python `memorized=True, hw_memorized=True`
- `memorized="true"` only → Python `memorized=True, hw_memorized=False`

---

## What Still Needs Attention

- **D02 firmware on Keithley unit 1**: The real fix is updating to D04. The AutoReconnect in Socket provides a software mitigation but the firmware drop is the root cause.
- **Network switch/router timeout**: Both Keithleys dropping connections suggests a network device may be killing idle TCP sessions. TCP keepalives (already attempted but reverted due to other bugs) or periodic heartbeat commands would help if confirmed.
- **ZI.py and ZI2.py** in `tango_servers_new/` still use the old `Device_4Impl` style — not ported to modern API yet.
