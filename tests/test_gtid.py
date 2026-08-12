from asyncmy.replication.gtid import Gtid, GtidSet

GTID = "57b70f4e-20d3-11e5-a393-4a63946f7eac:1-56"
OTHER = "4350f323-7565-4e59-8763-4b1b83a0ce0e:1-20"


def test_gtid_is_hashable():
    """GtidSet takes a set of Gtid, so Gtid must survive defining __eq__."""
    assert hash(Gtid(GTID)) == hash(Gtid(GTID))
    assert len({Gtid(GTID), Gtid(GTID)}) == 1


def test_distinct_gtids_stay_distinct():
    assert len({Gtid(GTID), Gtid(OTHER)}) == 2


def test_gtid_set_accepts_a_set():
    gtid_set = GtidSet({Gtid(GTID), Gtid(OTHER)})
    assert Gtid(GTID) in gtid_set


def test_gtid_set_is_hashable():
    assert hash(GtidSet({Gtid(GTID)})) == hash(GtidSet({Gtid(GTID)}))
