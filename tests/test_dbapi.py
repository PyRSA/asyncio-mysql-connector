import asyncmy


def test_pep249_globals():
    assert asyncmy.apilevel == "2.0"
    assert asyncmy.threadsafety == 1
    assert asyncmy.paramstyle == "pyformat"


def test_exceptions_exported():
    """PEP 249 requires the exception classes on the module."""
    for name in (
        "Warning",
        "Error",
        "InterfaceError",
        "DatabaseError",
        "DataError",
        "OperationalError",
        "IntegrityError",
        "InternalError",
        "ProgrammingError",
        "NotSupportedError",
    ):
        assert issubclass(getattr(asyncmy, name), Exception), name
    assert issubclass(asyncmy.OperationalError, asyncmy.DatabaseError)
    assert issubclass(asyncmy.DatabaseError, asyncmy.Error)
