# cython: boundscheck=False, wraparound=False, cdivision=True, initializedcheck=False

from cpython.bytearray cimport PyByteArray_AS_STRING, PyByteArray_GET_SIZE
from cpython.bytes cimport (PyBytes_AS_STRING, PyBytes_FromStringAndSize,
                            PyBytes_GET_SIZE)
from cpython.ref cimport Py_INCREF
from cpython.tuple cimport PyTuple_New, PyTuple_SET_ITEM
from cpython.unicode cimport PyUnicode_DecodeASCII, PyUnicode_DecodeUTF8
from libc.string cimport memchr

from .constants.FIELD_TYPE import VAR_STRING
from .constants.SERVER_STATUS import SERVER_MORE_RESULTS_EXISTS

include "charset.pxd"
from . import errors, structs

# Length-coded integer markers
# NULL_COLUMN = 251, UNSIGNED_CHAR_COLUMN = 251, UNSIGNED_SHORT_COLUMN = 252,
# UNSIGNED_INT24_COLUMN = 253, UNSIGNED_INT64_COLUMN = 254


cdef tuple _parse_row(const unsigned char *p, Py_ssize_t size, tuple converters):
    """Parse one text-protocol row directly from raw memory.

    ``converters`` holds one ``(code, encoding, converter)`` tuple per column:
    code 0 -> bytes, 1 -> utf8 decode, 2 -> ascii decode, 3 -> decode(encoding).
    """
    cdef:
        Py_ssize_t n = len(converters)
        Py_ssize_t pos = 0
        Py_ssize_t i, length
        unsigned int c
        int code
        tuple row = PyTuple_New(n)
        tuple conv
        object value, converter

    for i in range(n):
        if pos >= size:
            raise errors.InternalError("Truncated row packet")
        c = p[pos]
        pos += 1
        if c == 251:  # NULL
            Py_INCREF(None)
            PyTuple_SET_ITEM(row, i, None)
            continue
        if c < 251:
            length = <Py_ssize_t> c
        elif c == 252:
            length = <Py_ssize_t> (p[pos] | (p[pos + 1] << 8))
            pos += 2
        elif c == 253:
            length = <Py_ssize_t> (p[pos] | (p[pos + 1] << 8) | (p[pos + 2] << 16))
            pos += 3
        elif c == 254:
            length = <Py_ssize_t> (
                <unsigned long long> p[pos]
                | (<unsigned long long> p[pos + 1] << 8)
                | (<unsigned long long> p[pos + 2] << 16)
                | (<unsigned long long> p[pos + 3] << 24)
                | (<unsigned long long> p[pos + 4] << 32)
                | (<unsigned long long> p[pos + 5] << 40)
                | (<unsigned long long> p[pos + 6] << 48)
                | (<unsigned long long> p[pos + 7] << 56)
            )
            pos += 8
        else:
            raise errors.InternalError("Invalid length encoded integer in row")
        if pos + length > size:
            raise errors.InternalError("Truncated row packet")

        conv = <tuple> converters[i]
        code = <int> conv[0]
        if code == 0:
            value = PyBytes_FromStringAndSize(<const char *> (p + pos), length)
        elif code == 1:
            value = PyUnicode_DecodeUTF8(<const char *> (p + pos), length, NULL)
        elif code == 2:
            value = PyUnicode_DecodeASCII(<const char *> (p + pos), length, NULL)
        else:
            value = PyBytes_FromStringAndSize(<const char *> (p + pos), length).decode(<str> conv[1])
        pos += length

        converter = conv[2]
        if converter is not None:
            value = converter(value)
        Py_INCREF(value)
        PyTuple_SET_ITEM(row, i, value)
    return row


def parse_rows_from_buffer(bytearray buf, Py_ssize_t pos, tuple converters,
                           unsigned int seq_id, list rows):
    """Parse as many complete row packets as available in ``buf`` starting at ``pos``.

    Stops (without consuming) at the first packet that is incomplete, has a
    wrong sequence id, is an ERROR/EOF packet, is empty, or spans multiple
    wire packets (16MB). Parsed rows are appended to ``rows``.

    Returns ``(new_pos, new_seq_id)``.
    """
    cdef:
        const unsigned char *base = <const unsigned char *> PyByteArray_AS_STRING(buf)
        Py_ssize_t buf_len = PyByteArray_GET_SIZE(buf)
        Py_ssize_t payload_len
        unsigned int first

    while buf_len - pos >= 4:
        payload_len = <Py_ssize_t> (base[pos] | (base[pos + 1] << 8) | (base[pos + 2] << 16))
        if base[pos + 3] != seq_id:
            break  # sequence mismatch: let read_packet() raise the proper error
        if payload_len == 0 or payload_len == 0xFFFFFF:
            break  # empty or multi-packet payload: slow path
        if buf_len - pos - 4 < payload_len:
            break  # incomplete packet
        first = base[pos + 4]
        if first == 0xFF:
            break  # error packet
        if first == 0xFE and payload_len < 9:
            break  # EOF packet
        rows.append(_parse_row(base + pos + 4, payload_len, converters))
        pos += 4 + payload_len
        seq_id = (seq_id + 1) & 0xFF
    return pos, seq_id


cdef class MysqlPacket:
    """
    Representation of a MySQL response packet.
    Provides an interface for reading/parsing the packet results.
    """
    cdef:
        bytes _data
        const unsigned char *_ptr
        Py_ssize_t _size
        Py_ssize_t _position

    def __init__(self, bytes data, str encoding):
        self._position = 0
        self._data = data
        self._ptr = <const unsigned char *> PyBytes_AS_STRING(data)
        self._size = PyBytes_GET_SIZE(data)

    cpdef bytes get_all_data(self):
        return self._data

    cdef inline bytes _read_fast(self, Py_ssize_t size):
        """Fast internal read without bounds checking."""
        cdef Py_ssize_t pos = self._position
        self._position = pos + size
        return PyBytes_FromStringAndSize(<const char *> (self._ptr + pos), size)

    cpdef bytes read(self, Py_ssize_t size):
        """
        Read the first 'size' bytes in packet and advance cursor past them.
        """
        cdef Py_ssize_t pos = self._position
        if pos + size > self._size:
            error = (
                    "Result length not requested length:\n"
                    "Expected=%s.  Actual=%s.  Position: %s.  Data Length: %s"
                    % (size, self._size - pos, pos, self._size)
            )
            raise AssertionError(error)
        self._position = pos + size
        return PyBytes_FromStringAndSize(<const char *> (self._ptr + pos), size)

    cpdef bytes read_all(self):
        """Read all remaining data in the packet.

        (Subsequent read() will return errors.)
        """
        cdef bytes result = PyBytes_FromStringAndSize(
            <const char *> (self._ptr + self._position), self._size - self._position
        )
        self._position = 0
        return result

    cpdef advance(self, Py_ssize_t length):
        """
        Advance the cursor in data buffer 'length' bytes.
        """
        cdef Py_ssize_t new_position = self._position + length
        if new_position < 0 or new_position > self._size:
            raise Exception(
                "Invalid advance amount (%s) for cursor.  "
                "Position=%s" % (length, new_position)
            )
        self._position = new_position

    cpdef rewind(self, Py_ssize_t position=0):
        """
        Set the position of the data buffer cursor to 'position'.
        """
        if position < 0 or position > self._size:
            raise Exception("Invalid position to rewind cursor to: %s." % position)
        self._position = position

    cpdef bytes get_bytes(self, Py_ssize_t position, Py_ssize_t length=1):
        """
        Get 'length' bytes starting at 'position'.

        Position is start of payload (first four packet header bytes are not
        included) starting at index '0'.

        No error checking is done.  If requesting outside end of buffer
        an empty string (or string shorter than 'length') may be returned!
        """
        return self._data[position: (position + length)]

    cpdef unsigned int read_uint8(self):
        cdef unsigned int result = self._ptr[self._position]
        self._position += 1
        return result

    cpdef unsigned int read_uint16(self):
        cdef const unsigned char *p = self._ptr + self._position
        self._position += 2
        return p[0] | (p[1] << 8)

    cpdef unsigned int read_uint24(self):
        cdef const unsigned char *p = self._ptr + self._position
        self._position += 3
        return p[0] | (p[1] << 8) | (p[2] << 16)

    cpdef unsigned int read_uint32(self):
        cdef const unsigned char *p = self._ptr + self._position
        self._position += 4
        return p[0] | (p[1] << 8) | (p[2] << 16) | (<unsigned int> p[3] << 24)

    cpdef unsigned long long read_uint64(self):
        cdef const unsigned char *p = self._ptr + self._position
        self._position += 8
        return (
            <unsigned long long> p[0]
            | (<unsigned long long> p[1] << 8)
            | (<unsigned long long> p[2] << 16)
            | (<unsigned long long> p[3] << 24)
            | (<unsigned long long> p[4] << 32)
            | (<unsigned long long> p[5] << 40)
            | (<unsigned long long> p[6] << 48)
            | (<unsigned long long> p[7] << 56)
        )

    cpdef bytes read_string(self):
        cdef:
            const char *start = <const char *> (self._ptr + self._position)
            Py_ssize_t remaining = self._size - self._position
            const char *end
        end = <const char *> memchr(start, 0, remaining)
        if end == NULL:
            return None
        cdef bytes result = PyBytes_FromStringAndSize(start, end - start)
        self._position += (end - start) + 1
        return result

    cpdef read_length_encoded_integer(self):
        """
        Read a 'Length Coded Binary' number from the data buffer.

        Length coded numbers can be anywhere from 1 to 9 bytes depending
        on the value of the first byte.
        """
        cdef unsigned int c = self._ptr[self._position]
        self._position += 1
        if c == 251:  # NULL_COLUMN
            return None
        if c < 251:
            return c
        elif c == 252:
            return self.read_uint16()
        elif c == 253:
            return self.read_uint24()
        elif c == 254:
            return self.read_uint64()

    cpdef read_length_coded_string(self):
        """
        Read a 'Length Coded String' from the data buffer.

        A 'Length Coded String' consists first of a length coded
        (unsigned, positive) integer represented in 1-9 bytes followed by
        that many bytes of binary data.  (For example "cat" would be "3cat".)
        """
        cdef:
            unsigned int c
            Py_ssize_t length

        c = self._ptr[self._position]
        self._position += 1

        if c == 251:  # NULL
            return None
        if c < 251:
            length = <Py_ssize_t> c
        elif c == 252:
            length = <Py_ssize_t> self.read_uint16()
        elif c == 253:
            length = <Py_ssize_t> self.read_uint24()
        elif c == 254:
            length = <Py_ssize_t> self.read_uint64()
        else:
            return None
        return self._read_fast(length)

    cpdef tuple read_row(self, tuple converters):
        """Parse the whole packet as one text-protocol result row."""
        cdef tuple row = _parse_row(
            self._ptr + self._position, self._size - self._position, converters
        )
        self._position = self._size
        return row

    cpdef tuple read_struct(self, str fmt):
        s = getattr(structs, fmt[1:])
        result = s.unpack_from(self._data, self._position)
        self._position += s.size
        return tuple(result)

    cpdef int is_ok_packet(self):
        # https://dev.mysql.com/doc/internals/en/packet-OK_Packet.html
        return self._size >= 7 and self._ptr[0] == 0

    cpdef int is_eof_packet(self):
        # http://dev.mysql.com/doc/internals/en/generic-response-packets.html#packet-EOF_Packet
        # Caution: \xFE may be LengthEncodedInteger.
        # If \xFE is LengthEncodedInteger header, 8bytes followed.
        return self._size < 9 and self._size > 0 and self._ptr[0] == 0xFE

    cpdef int is_auth_switch_request(self):
        # http://dev.mysql.com/doc/internals/en/connection-phase-packets.html#packet-Protocol::AuthSwitchRequest
        return self._size > 0 and self._ptr[0] == 0xFE

    cpdef int is_extra_auth_data(self):
        # https://dev.mysql.com/doc/internals/en/successful-authentication.html
        return self._size > 0 and self._ptr[0] == 1

    cpdef int is_resultset_packet(self):
        return self._size > 0 and 1 <= self._ptr[0] <= 250

    cpdef int is_load_local_packet(self):
        return self._size > 0 and self._ptr[0] == 0xFB

    cpdef int is_error_packet(self):
        return self._size > 0 and self._ptr[0] == 0xFF

    def check_error(self):
        if self.is_error_packet():
            self.raise_for_error()

    cpdef raise_for_error(self):
        errors.raise_mysql_exception(self._data)

cdef class FieldDescriptorPacket(MysqlPacket):
    """
    A MysqlPacket that represents a specific column's metadata in the result.

    Parsing is automatically done and the results are exported via public
    attributes on the class such as: db, table_name, name, length, type_code.
    """
    cdef:
        bytes catalog, db
        public str table_name, org_table, name, org_name
        public long long charsetnr, length, type_code, flags, scale

    def __init__(self, bytes data, str encoding):
        super(FieldDescriptorPacket, self).__init__(data, encoding)
        self._parse_field_descriptor(encoding)

    cdef _parse_field_descriptor(self, str encoding):
        """
        Parse the 'Field Descriptor' (Metadata) packet.

        This is compatible with MySQL 4.1+ (not compatible with MySQL 4.0).
        """
        self.catalog = self.read_length_coded_string()
        self.db = self.read_length_coded_string()
        self.table_name = self.read_length_coded_string().decode(encoding)
        self.org_table = self.read_length_coded_string().decode(encoding)
        self.name = self.read_length_coded_string().decode(encoding)
        self.org_name = self.read_length_coded_string().decode(encoding)
        # layout: filler(1) charsetnr(2) length(4) type_code(1) flags(2) scale(1) filler(2)
        self._position += 1
        self.charsetnr = self.read_uint16()
        self.length = self.read_uint32()
        self.type_code = self.read_uint8()
        self.flags = self.read_uint16()
        self.scale = self.read_uint8()
        self._position += 2

    cpdef description(self):
        """Provides a 7-item tuple compatible with the Python PEP249 DB Spec."""
        cdef int column_length = self.get_column_length()
        return (
            self.name,
            self.type_code,
            None,  # TODO: display_length; should this be self.length?
            column_length,  # 'internal_size'
            column_length,  # 'precision'  # TODO: why!?!?
            self.scale,
            self.flags % 2 == 0,
        )

    cdef int get_column_length(self):
        if self.type_code == VAR_STRING:
            mb_len = MB_LENGTH.get(self.charsetnr, 1)
            return self.length // mb_len
        return self.length

    def __str__(self):
        return "%s %r.%r.%r, type=%s, flags=%x" % (
            self.__class__,
            self.db,
            self.table_name,
            self.name,
            self.type_code,
            self.flags,
        )

cdef class OKPacketWrapper:
    """
    OK Packet Wrapper. It uses an existing packet object, and wraps
    around it, exposing useful variables while still providing access
    to the original packet objects variables and methods.
    """
    cdef:
        MysqlPacket packet
        public int server_status, warning_count, has_next
        public bytes message
        public unsigned long long affected_rows, insert_id

    def __init__(self, MysqlPacket from_packet):
        if not from_packet.is_ok_packet():
            raise ValueError(
                "Cannot create "
                + str(self.__class__.__name__)
                + " object from invalid packet type"
            )

        self.packet = from_packet
        self.packet.advance(1)

        self.affected_rows = self.packet.read_length_encoded_integer()
        self.insert_id = self.packet.read_length_encoded_integer()
        self.server_status = self.packet.read_uint16()
        self.warning_count = self.packet.read_uint16()
        self.message = self.packet.read_all()
        self.has_next = self.server_status & SERVER_MORE_RESULTS_EXISTS

    def __getattr__(self, key):
        return getattr(self.packet, key)

cdef class EOFPacketWrapper:
    """
    EOF Packet Wrapper. It uses an existing packet object, and wraps
    around it, exposing useful variables while still providing access
    to the original packet objects variables and methods.
    """
    cdef:
        MysqlPacket packet
        public int server_status, warning_count, has_next

    def __init__(self, MysqlPacket from_packet):
        if not from_packet.is_eof_packet():
            raise ValueError(
                f"Cannot create '{self.__class__}' object from invalid packet type"
            )

        self.packet = from_packet
        self.packet.advance(1)
        self.warning_count = self.packet.read_uint16()
        self.server_status = self.packet.read_uint16()
        self.has_next = self.server_status & SERVER_MORE_RESULTS_EXISTS

    def __getattr__(self, key):
        return getattr(self.packet, key)

cdef class LoadLocalPacketWrapper:
    """
    Load Local Packet Wrapper. It uses an existing packet object, and wraps
    around it, exposing useful variables while still providing access
    to the original packet objects variables and methods.
    """
    cdef:
        MysqlPacket packet
        public bytes filename

    def __init__(self, MysqlPacket from_packet):
        if not from_packet.is_load_local_packet():
            raise ValueError(
                f"Cannot create '{self.__class__}' object from invalid packet type"
            )

        self.packet = from_packet
        self.filename = self.packet.get_all_data()[1:]

    def __getattr__(self, key):
        return getattr(self.packet, key)
