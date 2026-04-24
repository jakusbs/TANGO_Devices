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
    - AutoReconnect: Reconnect automatically on connection loss (default True)
    """

    Hostname      = device_property(dtype='str',  mandatory=True,       doc="Remote hostname or IP address")
    Port          = device_property(dtype='int',  mandatory=True,       doc="TCP port number")
    Readtimeout   = device_property(dtype='int',  default_value=1000,   doc="Read timeout in milliseconds")
    AutoReconnect = device_property(dtype='bool', default_value=True,   doc="Reconnect automatically on connection loss")

    def init_device(self):
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

    def _on_socket_error(self, exc):
        """Mark connection broken; reconnect immediately if AutoReconnect is enabled."""
        self.error_stream("Socket error: {}".format(exc))
        try:
            if self._sock is not None:
                self._sock.close()
        except Exception:
            pass
        self._sock = None
        self.set_state(DevState.FAULT)
        self.set_status("Connection lost: {}".format(exc))
        if self.AutoReconnect:
            try:
                self._connect()
                self.set_state(DevState.ON)
                self.set_status("Reconnected to {}:{}".format(self.Hostname, self.Port))
                self.info_stream("Auto-reconnected to {}:{}".format(self.Hostname, self.Port))
            except Exception as e:
                self.set_status("Reconnect failed: {}".format(e))

    def _require_connected(self):
        """Ensure the socket is open; auto-reconnect if AutoReconnect is enabled."""
        if self._sock is None:
            if self.AutoReconnect:
                try:
                    self._connect()
                    self.set_state(DevState.ON)
                    self.set_status("Reconnected to {}:{}".format(self.Hostname, self.Port))
                    self.info_stream("Auto-reconnected to {}:{}".format(self.Hostname, self.Port))
                    return
                except Exception as e:
                    self.set_status("Reconnect failed: {}".format(e))
            tango.Except.throw_exception(
                "Socket not connected",
                "Socket is in FAULT state — call Reconnect first",
                "Socket::_require_connected")

    # ---- Commands -------------------------------------------------------

    @command(dtype_in='DevString', doc_in="String to send")
    def Write(self, argin):
        """Send a string to the socket (no newline appended)."""
        self._require_connected()
        try:
            self._sock.sendall(argin.encode())
        except _socket.error as e:
            self._on_socket_error(e)
            raise

    @command(dtype_out='DevString', doc_out="Received string")
    def Read(self):
        """Read available data from the socket."""
        self._require_connected()
        try:
            data = self._sock.recv(4096)
            return data.decode()
        except _socket.error as e:
            self._on_socket_error(e)
            raise

    @command()
    def Reconnect(self):
        """Close and reopen the TCP connection."""
        try:
            self._connect()
            self.set_state(DevState.ON)
            self.set_status("Connected to {}:{}".format(self.Hostname, self.Port))
        except Exception as e:
            self.set_state(DevState.FAULT)
            self.set_status("Reconnect failed: {} — try again in a few seconds".format(e))

    @command(dtype_in='DevString', doc_in="String to send",
             dtype_out='DevString', doc_out="Received string")
    def WriteAndRead(self, argin):
        """Write a string then immediately read the response."""
        self._require_connected()
        try:
            self._sock.sendall(argin.encode())
            data = self._sock.recv(4096)
            return data.decode()
        except _socket.error as e:
            self._on_socket_error(e)
            raise

    @command(dtype_out='DevString', doc_out="Line read from socket (strips trailing newline)")
    def Readln(self):
        """Read characters until a newline character is received."""
        self._require_connected()
        try:
            buf = b''
            while True:
                c = self._sock.recv(1)
                if not c or c == b'\n':
                    break
                buf += c
            return buf.decode()
        except _socket.error as e:
            self._on_socket_error(e)
            raise

    @command(dtype_in='DevString', doc_in="Terminator string",
             dtype_out='DevString', doc_out="Data read up to and including the terminator")
    def ReadUntil(self, argin):
        """Read characters until the given terminator string is received."""
        self._require_connected()
        try:
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
        except _socket.error as e:
            self._on_socket_error(e)
            raise

    @command(dtype_in=('str',), doc_in="[write_string, terminator]",
             dtype_out='DevString', doc_out="Response up to and including the terminator")
    def WriteReadUntil(self, argin):
        """Write argin[0], then read until argin[1] is received."""
        self._require_connected()
        try:
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
        except _socket.error as e:
            self._on_socket_error(e)
            raise

    @command(dtype_in='DevString', doc_in="String to send (newline appended)")
    def WriteLine(self, argin):
        """Send a string followed by a newline character."""
        self._require_connected()
        try:
            self._sock.sendall((argin + '\n').encode())
        except _socket.error as e:
            self._on_socket_error(e)
            raise

    @command(dtype_in='DevString', doc_in="String to send",
             dtype_out='DevString', doc_out="Received string")
    def WriteRead(self, argin):
        """Write a string then read the response."""
        self._require_connected()
        try:
            self._sock.sendall(argin.encode())
            data = self._sock.recv(4096)
            return data.decode()
        except _socket.error as e:
            self._on_socket_error(e)
            raise

    @command(dtype_in='DevString', doc_in="String to send",
             dtype_out='DevString', doc_out="Response up to the null character")
    def WriteReadZero(self, argin):
        """Write a string then read characters until a null byte is received."""
        self._require_connected()
        try:
            self._sock.sendall(argin.encode())
            buf = b''
            while True:
                c = self._sock.recv(1)
                if not c or c == b'\x00':
                    break
                buf += c
            return buf.decode()
        except _socket.error as e:
            self._on_socket_error(e)
            raise

    @command(dtype_out='DevString', doc_out="Single character read from socket")
    def ReadChar(self):
        """Read a single character from the socket."""
        self._require_connected()
        try:
            c = self._sock.recv(1)
            return c.decode()
        except _socket.error as e:
            self._on_socket_error(e)
            raise


def main(args=None, **kwargs):
    return run((Socket,), args=args, **kwargs)


if __name__ == '__main__':
    main()
