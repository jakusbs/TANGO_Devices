# -*- coding: utf-8 -*-
"""
Socket
TCP socket gateway device server.
Wraps a raw TCP connection as a TANGO device, providing read/write commands.
Used by ANC300, PyKeithley, and PyKeithley2.
"""

import socket as _socket

import tango
from tango import DevState
from tango.server import Device, command, device_property, run

__all__ = ["Socket", "main"]


class Socket(Device):
    """
    TCP socket gateway. Opens a persistent TCP connection to Hostname:Port
    and exposes read/write commands for use by other TANGO devices.

    **Properties:**
    - Hostname: Remote host to connect to
    - Port: TCP port number
    - Readtimeout: Socket read timeout in milliseconds (default 1000)
    """

    Hostname = device_property(dtype='str', mandatory=True, doc="Remote hostname or IP address")
    Port = device_property(dtype='int', mandatory=True, doc="TCP port number")
    Readtimeout = device_property(dtype='int', default_value=1000, doc="Read timeout in milliseconds")

    def init_device(self):
        """Initialise the device and open the TCP connection."""
        Device.init_device(self)
        self._sock = None
        try:
            self._connect()
            self.set_state(DevState.ON)
        except Exception as e:
            self.error_stream("Socket.init_device: {}".format(e))
            self.set_state(DevState.FAULT)
            self.set_status("Could not connect to {}:{} - {}".format(self.Hostname, self.Port, e))

    def delete_device(self):
        """Close the socket on device destruction."""
        if self._sock is not None:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None

    def _connect(self):
        """Open (or reopen) the TCP connection."""
        if self._sock is not None:
            try:
                self._sock.close()
            except Exception:
                pass
        s = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
        s.settimeout(self.Readtimeout / 1000.0)
        s.connect((self.Hostname, self.Port))
        self._sock = s

    # ---- Commands -------------------------------------------------------

    @command(dtype_in='DevString', doc_in="String to send")
    def Write(self, argin):
        """Send a string to the socket (no newline appended)."""
        self._sock.sendall(argin.encode())

    @command(dtype_out='DevString', doc_out="Received string")
    def Read(self):
        """Read available data from the socket."""
        data = self._sock.recv(4096)
        return data.decode()

    @command()
    def Reconnect(self):
        """Close and reopen the TCP connection."""
        self._connect()
        self.set_state(DevState.ON)

    @command(dtype_in='DevString', doc_in="String to send",
             dtype_out='DevString', doc_out="Received string")
    def WriteAndRead(self, argin):
        """Write a string then immediately read the response."""
        self._sock.sendall(argin.encode())
        data = self._sock.recv(4096)
        return data.decode()

    @command(dtype_out='DevString', doc_out="Line read from socket (strips trailing newline)")
    def Readln(self):
        """Read characters until a newline character is received."""
        buf = b''
        while True:
            c = self._sock.recv(1)
            if not c or c == b'\n':
                break
            buf += c
        return buf.decode()

    @command(dtype_in='DevString', doc_in="Terminator string",
             dtype_out='DevString', doc_out="Data read up to and including the terminator")
    def ReadUntil(self, argin):
        """Read characters until the given terminator string is received."""
        buf = b''
        term = argin.encode()
        while True:
            c = self._sock.recv(1)
            if not c:
                break
            buf += c
            if buf.endswith(term):
                break
        return buf.decode()

    @command(dtype_in=('str',), doc_in="[write_string, terminator]",
             dtype_out='DevString', doc_out="Response up to and including the terminator")
    def WriteReadUntil(self, argin):
        """Write argin[0], then read until argin[1] is received."""
        write_str = argin[0]
        terminator = argin[1]
        self._sock.sendall(write_str.encode())
        buf = b''
        term = terminator.encode()
        while True:
            c = self._sock.recv(1)
            if not c:
                break
            buf += c
            if buf.endswith(term):
                break
        return buf.decode()

    @command(dtype_in='DevString', doc_in="String to send (newline appended)")
    def WriteLine(self, argin):
        """Send a string followed by a newline character."""
        self._sock.sendall((argin + '\n').encode())

    @command(dtype_in='DevString', doc_in="String to send",
             dtype_out='DevString', doc_out="Received string")
    def WriteRead(self, argin):
        """Write a string then read the response."""
        self._sock.sendall(argin.encode())
        data = self._sock.recv(4096)
        return data.decode()

    @command(dtype_in='DevString', doc_in="String to send",
             dtype_out='DevString', doc_out="Response up to the null character")
    def WriteReadZero(self, argin):
        """Write a string then read characters until a null byte is received."""
        self._sock.sendall(argin.encode())
        buf = b''
        while True:
            c = self._sock.recv(1)
            if not c or c == b'\x00':
                break
            buf += c
        return buf.decode()

    @command(dtype_out='DevString', doc_out="Single character read from socket")
    def ReadChar(self):
        """Read a single character from the socket."""
        c = self._sock.recv(1)
        return c.decode()


def main(args=None, **kwargs):
    return run((Socket,), args=args, **kwargs)


if __name__ == '__main__':
    main()
