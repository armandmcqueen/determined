"""
tunnel.py will tunnel a TCP connection through Determined master at MASTER_ADDR to SERVICE_UUID.

This is used to tunnel ssh connections through the master, where the hostname in the SERVICE_UUID
should be the shell ID of the shell in question.
"""

import argparse
import http.client
import io
import os
import socket
import ssl
import sys
import threading
from typing import Any, Optional, Union

from determined_common.api import request


class HTTPSProxyConnection(http.client.HTTPSConnection):
    """
    A connection class that applies TLS to the entire connection, even for CONNECT requests.
    """

    def __init__(self, cert_name: Optional[str], *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._cert_name = cert_name

    def connect(self) -> None:
        self.sock = self._create_connection(  # type: ignore
            (self.host, self.port), self.timeout, self.source_address  # type: ignore
        )
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

        # This is what differs from the base class: we wrap the socket *before* setting up the
        # tunnel and verify against the proxy's hostname rather than the target's.  We also support
        # matching the host name against an externally-provided hostname.
        self.sock = self._context.wrap_socket(  # type: ignore
            self.sock, server_hostname=self._cert_name or self.host
        )

        if self._tunnel_host:  # type: ignore
            self._tunnel()  # type: ignore


class SocketWrapper:
    """A small wrapper to provide file-like read/write methods on top of a socket object."""

    def __init__(self, sock: socket.socket):
        self.sock = sock

    def read(self, n: int) -> bytes:
        return self.sock.recv(n)

    def write(self, s: bytes) -> int:
        self.sock.sendall(s)
        return len(s)

    def close(self) -> None:
        self.sock.close()


class Copier(threading.Thread):
    """
    A thread to copy from one file descriptor to another.  Only copies in one direction; use two
    threads to deal with bidirectional file descriptors.  The choice to use a pair of threads as
    opposed to select.select or select.poll ensures that this code will run nicely on Windows.
    """

    def __init__(
        self, src: Union[SocketWrapper, io.RawIOBase], dst: Union[SocketWrapper, io.RawIOBase]
    ):
        super().__init__()
        self.src = src
        self.dst = dst

    def run(self) -> None:
        try:
            while True:
                try:
                    buf = self.src.read(4096)
                except OSError:
                    break
                if not buf:
                    break
                try:
                    self.dst.write(buf)
                except OSError:
                    break
        finally:
            # We're ok with double-closing some sockets.
            try:
                self.src.close()
            except OSError:
                pass

            try:
                self.dst.close()
            except OSError:
                pass


def http_connect_tunnel(
    master: str, service: str, cert_file: Optional[str], cert_name: Optional[str]
) -> None:
    parsed_master = request.parse_master_address(master)
    assert parsed_master.hostname is not None, "Failed to parse master address: {}".format(master)

    if parsed_master.scheme == "https":
        context = ssl.create_default_context(cafile=cert_file)
        client = HTTPSProxyConnection(
            cert_name, parsed_master.hostname, parsed_master.port, context=context
        )  # type: http.client.HTTPConnection
    else:
        client = http.client.HTTPConnection(parsed_master.hostname, parsed_master.port)

    client.set_tunnel(service)

    try:
        client.connect()
    except socket.gaierror:
        print("failed to look up host:", master, file=sys.stderr)
        raise

    with client.sock as sock:
        sock = SocketWrapper(sock)
        # Directly using sys.stdin.buffer.read or sys.stdout.buffer.write would block due to
        # buffering; instead, we use unbuffered file objects based on the same file descriptors.
        unbuffered_stdin = os.fdopen(sys.stdin.fileno(), "rb", buffering=0)
        unbuffered_stdout = os.fdopen(sys.stdout.fileno(), "wb", buffering=0)

        c1 = Copier(sock, unbuffered_stdout)
        c2 = Copier(unbuffered_stdin, sock)
        c1.start()
        c2.start()
        c1.join()
        c2.join()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Tunnel through a Determined master")
    parser.add_argument("master_addr")
    parser.add_argument("service_uuid")
    parser.add_argument("--cert-file")
    parser.add_argument("--cert-name")
    args = parser.parse_args()

    http_connect_tunnel(args.master_addr, args.service_uuid, args.cert_file, args.cert_name)
