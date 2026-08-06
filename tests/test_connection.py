import re

import pytest

from asyncmy.connection import Connection
from asyncmy.errors import OperationalError


@pytest.mark.asyncio
async def test_connect(connection_kwargs):
    connection = Connection(**connection_kwargs)
    await connection.connect()
    assert connection._connected
    assert re.match(
        r"\d+\.\d+\.\d+([^0-9].*)?",
        connection.get_server_info(),
    )
    assert connection.get_proto_info() == 10
    assert connection.get_host_info() != "Not Connected"
    await connection.ensure_closed()


@pytest.mark.asyncio
async def test_read_timeout(connection_kwargs):
    with pytest.raises(OperationalError):
        connection = Connection(read_timeout=1, **connection_kwargs)
        await connection.connect()
        async with connection.cursor() as cursor:
            await cursor.execute("DO SLEEP(3)")


@pytest.mark.asyncio
async def test_ping_reconnect_refreshes_password(mocker):
    class ReconnectAttempt(Exception):
        pass

    password_creator = mocker.Mock(return_value="fresh-password")
    connection = Connection(password_creator=password_creator)
    connection._connected = True
    mocker.patch.object(
        connection,
        "_execute_command",
        side_effect=OperationalError("connection lost"),
    )
    mocker.patch.object(
        connection._loop,
        "create_connection",
        side_effect=ReconnectAttempt,
    )

    with pytest.raises(ReconnectAttempt):
        await connection.ping(reconnect=True)

    password_creator.assert_called_once_with()


@pytest.mark.asyncio
async def test_transaction(connection):
    await connection.begin()
    await connection.query(
        """INSERT INTO test.asyncmy(`decimal`, date, datetime, `float`,
         string, `tinyint`) VALUES (%s,'%s','%s',%s,'%s',%s)"""
        % (
            1,
            "2020-08-08",
            "2020-08-08 00:00:00",
            1,
            "1",
            1,
        ),
        True,
    )
    await connection.rollback()
