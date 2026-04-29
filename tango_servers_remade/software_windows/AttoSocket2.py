# AttoSocket2.py — Windows-side UDP bridge for the AttoDRY2100
# Listens for commands from the Linux TANGO server and translates them
# into PyAttoDRY DLL calls.
#
# Protocol (UDP, all ASCII):
#   TANGO → Windows  "start"      — initial handshake
#   TANGO → Windows  "ON"         — begin()+Connect() AttoDRY
#   TANGO → Windows  "Read"       — fetch telemetry, reply with CSV packet
#   TANGO → Windows  "W001:<v>"   — setUserMagneticField (T)
#   TANGO → Windows  "W002:<v>"   — setUserTemperature (K)
#   TANGO → Windows  "W003"       — toggleMagneticFieldControl
#   TANGO → Windows  "W004"       — toggleFullTemperatureControl
#   TANGO → Windows  "W005"       — togglePersistentMode
#   TANGO → Windows  "W006"       — goToBaseTemperature
#   TANGO → Windows  "W007"       — startSampleExchange
#   TANGO → Windows  "W008"       — sweepFieldToZero
#   TANGO → Windows  "W009"       — Cancel
#   TANGO → Windows  "W010"       — lowerError
#   TANGO → Windows  "W011"       — toggleStartUpShutdown
#   TANGO → Windows  "W012"       — toggleSampleTemperatureControl
#   TANGO → Windows  "OFF"        — Disconnect()+end(), close socket
#
# Reply packet (on "Read") — CSV, 26 fields after "Read:":
#   idx  field                      idx  field
#    0   isControllingField          13  getSampleHeaterPower
#    1   isControllingTemperature    14  getMagneticFieldSetPoint
#    2   isPersistentModeSet         15  getUserTemperature
#    3   getMagneticField            16  getTurbopumpFrequency
#    4   getSampleTemperature        17  getCryostatOutPressure
#    5   getVtiTemperature           18  isGoingToBaseTemperature
#    6   get4KStageTemperature       19  isSampleExchangeInProgress
#    7   get40KStageTemperature      20  isSampleReadyToExchange
#    8   getReservoirTemperature     21  isZeroingField
#    9   getCryostatInPressure       22  isPumping
#   10   getDumpPressure             23  isSystemRunning
#   11   getReservoirHeaterPower     24  isExchangeHeaterOn
#   12   getVtiHeaterPower           25  isSampleHeaterOn

from PyAttoDRY import AttoDRY
import socket
import time

# ── Configuration ─────────────────────────────────────────────────────────────
HOST           = '192.168.1.8'  # IP of this Windows PC
PORT           = 11000          # UDP port to listen on
COM_PORT       = 'COM4'         # COM port connected to AttoDRY2100
RECV_TIMEOUT_S = 10.0           # seconds before recvfrom times out
CONNECT_WAIT_S = 10             # seconds to wait for AttoDRY to initialise
# ─────────────────────────────────────────────────────────────────────────────


def build_packet():
    """Read all telemetry from the DLL and return the CSV packet string.
    Returns None if any call fails."""
    try:
        iCF  = AttoDRY.isControllingField()
        iCT  = AttoDRY.isControllingTemperature()
        iCP  = AttoDRY.isPersistentModeSet()
        gMF  = AttoDRY.getMagneticField()
        gST  = AttoDRY.getSampleTemperature()
        gVT  = AttoDRY.getVtiTemperature()
        gMT  = AttoDRY.get4KStageTemperature()
        g40K = AttoDRY.get40KStageTemperature()
        gRT  = AttoDRY.getReservoirTemperature()
        gCIP = AttoDRY.getCryostatInPressure()
        gDP  = AttoDRY.getDumpPressure()
        gRHP = AttoDRY.getReservoirHeaterPower()
        gVHP = AttoDRY.getVtiHeaterPower()
        gVSP = AttoDRY.getSampleHeaterPower()
        gMFS = AttoDRY.getMagneticFieldSetPoint()
        gUT  = AttoDRY.getUserTemperature()
        gTPF = AttoDRY.getTurbopumpFrequency()
        gCoP = AttoDRY.getCryostatOutPressure()
        iGBT = AttoDRY.isGoingToBaseTemperature()
        iSEP = AttoDRY.isSampleExchangeInProgress()
        iSRE = AttoDRY.isSampleReadyToExchange()
        iZF  = AttoDRY.isZeroingField()
        iPmp = AttoDRY.isPumping()
        iSR  = AttoDRY.isSystemRunning()
        iEH  = AttoDRY.isExchangeHeaterOn()
        iSH  = AttoDRY.isSampleHeaterOn()
    except Exception as e:
        print(f'[AttoSocket2] Read error: {e}')
        return None

    fields = [
        iCF, iCT, iCP,
        gMF, gST, gVT, gMT, g40K, gRT,
        gCIP, gDP, gRHP, gVHP, gVSP,
        gMFS, gUT, gTPF, gCoP,
        iGBT, iSEP, iSRE, iZF, iPmp, iSR, iEH, iSH,
    ]
    return 'Read:' + ','.join(str(f) for f in fields)


def connect_attodry():
    """Call begin()+Connect() and wait for the AttoDRY to initialise.
    Returns True if connected and initialised."""
    print('[AttoSocket2] Connecting to AttoDRY...')
    try:
        AttoDRY.begin(setup_version=1)
        AttoDRY.Connect(COMPort=COM_PORT)
    except Exception as e:
        print(f'[AttoSocket2] begin/Connect failed: {e}')
        return False

    for _ in range(CONNECT_WAIT_S):
        time.sleep(1.0)
        try:
            if AttoDRY.isDeviceInitialised() and AttoDRY.isDeviceConnected():
                print('[AttoSocket2] AttoDRY initialised and connected.')
                return True
        except Exception as e:
            print(f'[AttoSocket2] Init check error: {e}')
    print('[AttoSocket2] AttoDRY did not initialise within timeout.')
    return False


def main():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(RECV_TIMEOUT_S)
    s.bind((HOST, PORT))
    print(f'[AttoSocket2] Listening on {HOST}:{PORT}')

    last_packet = None
    addr = None

    try:
        while True:
            # ── Receive ───────────────────────────────────────────────────
            try:
                raw, addr = s.recvfrom(256)
            except socket.timeout:
                print('[AttoSocket2] No data from TANGO (timeout). Waiting...')
                continue
            except OSError as e:
                print(f'[AttoSocket2] Socket error: {e}')
                break

            try:
                data = raw.decode('utf-8').strip()
            except UnicodeDecodeError:
                continue

            # ── Dispatch ──────────────────────────────────────────────────
            if data in ('start', 'ON'):
                # ACK immediately — DLL init can take up to CONNECT_WAIT_S s,
                # TANGO Connect() has a 5 s recvfrom timeout.
                s.sendto(b'ON', addr)
                connect_attodry()

            elif data == 'Read':
                try:
                    if not (AttoDRY.isDeviceConnected() and AttoDRY.isDeviceInitialised()):
                        print('[AttoSocket2] AttoDRY not ready — resending last packet.')
                        if last_packet:
                            s.sendto(last_packet.encode('utf-8'), addr)
                        continue
                except Exception:
                    pass

                pkt = build_packet()
                if pkt is not None:
                    last_packet = pkt
                    s.sendto(pkt.encode('utf-8'), addr)
                elif last_packet is not None:
                    s.sendto(last_packet.encode('utf-8'), addr)

            elif data.startswith('W'):
                try:
                    if data[:4] == 'W001':
                        AttoDRY.setUserMagneticField(float(data[5:]))
                    elif data[:4] == 'W002':
                        AttoDRY.setUserTemperature(float(data[5:]))
                    elif data == 'W003':
                        AttoDRY.toggleMagneticFieldControl()
                    elif data == 'W004':
                        AttoDRY.toggleFullTemperatureControl()
                    elif data == 'W005':
                        AttoDRY.togglePersistentMode()
                    elif data == 'W006':
                        AttoDRY.goToBaseTemperature()
                    elif data == 'W007':
                        AttoDRY.startSampleExchange()
                    elif data == 'W008':
                        AttoDRY.sweepFieldToZero()
                    elif data == 'W009':
                        AttoDRY.Cancel()
                    elif data == 'W010':
                        AttoDRY.lowerError()
                    elif data == 'W011':
                        AttoDRY.toggleStartUpShutdown()
                    elif data == 'W012':
                        AttoDRY.toggleSampleTemperatureControl()
                except Exception as e:
                    print(f'[AttoSocket2] Write command {data!r} failed: {e}')

            elif data == 'OFF':
                print('[AttoSocket2] Received OFF — disconnecting.')
                try:
                    AttoDRY.Disconnect()
                    AttoDRY.end()
                except Exception as e:
                    print(f'[AttoSocket2] Disconnect error: {e}')
                s.sendto(b'OFF', addr)
                break

    except KeyboardInterrupt:
        print('\n[AttoSocket2] Interrupted by user.')
        try:
            AttoDRY.Disconnect()
            AttoDRY.end()
        except Exception:
            pass
    finally:
        s.close()
        print('[AttoSocket2] Socket closed.')


if __name__ == '__main__':
    main()
