#!/usr/bin/env python
# -*- coding: utf-8 -*-

import threading
import socket
import re
import time

class AttoDRYThread3(threading.Thread):
    """
    Background listener thread for AttoDRY UDP packets.
    This thread runs continuously, receives incoming "ReadA..." packets,
    parses them, and passes them to the Device class to update internal values.
    """

    def __init__(self, parent):
        """
        parent: instance of the AttoDRY Device class. It must provide:
          - self.s: an already created and bound UDP socket
          - self._parse_and_store(string): a method to process the "ReadA..." content
        """
        super().__init__(daemon=True)
        self.p = parent
        # Buffer size: must be large enough to hold the complete "ReadA..." packet
        self.bufsize = 256

    def run(self):
        # Set a short timeout so recvfrom() does not block indefinitely
        try:
            self.p.s.settimeout(0.1)
        except Exception:
            # If the socket does not exist or is already closed, exit
            return

        while True:
            try:
                data, addr = self.p.s.recvfrom(self.bufsize)
            except socket.timeout:
                # No packet within 0.1 s, loop again
                continue
            except OSError:
                # Socket has been closed ? stop the thread
                return

            # Decode bytes into UTF-8 string
            try:
                s = data.decode('utf-8')
            except UnicodeDecodeError:
                continue

            # Only process packets that start with "ReadA"
            if not s.startswith('ReadA'):
                continue

            # Hand off to the Device class to parse and store
            try:
                self.p._parse_and_store(s)
            except Exception:
                # If parsing fails, continue listening
                continue
