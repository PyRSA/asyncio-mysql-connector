import asyncio
import datetime
import socket
import ssl

import pytest

from asyncmy import connect
from asyncmy.errors import OperationalError
from conftest import connection_kwargs

HOST = connection_kwargs["host"]
PORT = connection_kwargs["port"]
AUTH = {k: v for k, v in connection_kwargs.items() if k not in ("host", "port")}


def _connected_sock(host=HOST, port=PORT):
    sock = socket.create_connection((host, port))
    sock.setblocking(False)
    return sock


@pytest.mark.asyncio
async def test_connect_with_sock():
    connection = await connect(sock=_connected_sock(), **AUTH)
    async with connection.cursor() as cursor:
        await cursor.execute("SELECT 1")
        assert await cursor.fetchone() == (1,)
    await connection.ensure_closed()


@pytest.mark.asyncio
async def test_sock_cannot_be_reconnected():
    """A used socket must fail loudly rather than silently dial host/port."""
    connection = await connect(sock=_connected_sock(), **AUTH)
    connection.close()
    connection._connected = False
    with pytest.raises(OperationalError, match="Cannot reconnect"):
        await connection.connect()


def _self_signed(tmp_path):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=5))
        .not_valid_after(now + datetime.timedelta(hours=1))
        .sign(key, hashes.SHA256())
    )
    cert_file = tmp_path / "cert.pem"
    key_file = tmp_path / "key.pem"
    cert_file.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_file.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
    )
    return cert_file, key_file


@pytest.mark.asyncio
async def test_sock_with_externally_established_tls(tmp_path):
    """The Cloud SQL shape: a TLS proxy in front of MySQL, so TLS is set up by
    the caller and the in-protocol STARTTLS upgrade must be skipped."""
    cert_file, key_file = _self_signed(tmp_path)

    async def pipe(reader, writer):
        try:
            while data := await reader.read(65536):
                writer.write(data)
                await writer.drain()
        except (ConnectionError, asyncio.CancelledError):
            pass
        finally:
            writer.close()

    async def handle(client_reader, client_writer):
        upstream_reader, upstream_writer = await asyncio.open_connection(HOST, PORT)
        await asyncio.gather(
            pipe(client_reader, upstream_writer), pipe(upstream_reader, client_writer)
        )

    server_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server_ctx.load_cert_chain(cert_file, key_file)
    server = await asyncio.start_server(handle, "127.0.0.1", 0, ssl=server_ctx)
    proxy_port = server.sockets[0].getsockname()[1]

    async with server:
        client_ctx = ssl.create_default_context(cafile=str(cert_file))
        client_ctx.check_hostname = False
        connection = await connect(
            sock=_connected_sock("127.0.0.1", proxy_port),
            ssl=client_ctx,
            host="localhost",
            **AUTH,
        )
        assert connection._secure
        async with connection.cursor() as cursor:
            await cursor.execute("SELECT 1")
            assert await cursor.fetchone() == (1,)
            # Empty because the driver never ran STARTTLS: the encryption
            # lives between us and the proxy, not the proxy and the server.
            await cursor.execute("SHOW STATUS LIKE 'Ssl_cipher'")
            assert (await cursor.fetchone())[1] == ""
        await connection.ensure_closed()
