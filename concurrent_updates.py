#! /usr/bin/env python

import psycopg, traceback
from psycopg import IsolationLevel, Connection
from argparse import ArgumentParser

parser = ArgumentParser()
parser.add_argument(
    "isolation_level",
    choices=["ru", "rc", "rr", "s"],
    help="""
isolation level:
ru (read uncomitted)
rc (read committed)
rr (repeatable reads)
s (serializable)
""",
)
parser.add_argument(
    "--serial",
    "-s",
    action="store_true",
    help="""
    whether to serialize transaction execution or interleave them. Serialized execution will never cause a serialization error
    """,
)

args = parser.parse_args()

isolation_level_map = {
    "ru": IsolationLevel.READ_UNCOMMITTED,
    "rc": IsolationLevel.READ_COMMITTED,
    "rr": IsolationLevel.REPEATABLE_READ,
    "s": IsolationLevel.SERIALIZABLE,
}


target_isolation_level = isolation_level_map[args.isolation_level]

COUNTER_NAME = "a"


def open_connection() -> Connection:
    return psycopg.connect(
        "postgresql://postgres:postgres@localhost/postgres", autocommit=False
    )


def init_counter(conn: Connection):
    conn.execute(
        "CREATE TABLE IF NOT EXISTS counter (name text primary key, value int)"
    )
    conn.execute(
        "INSERT INTO counter VALUES (%(name)s, %(value)s) ON CONFLICT ON CONSTRAINT counter_pkey DO UPDATE SET value = %(value)s",
        dict(name=COUNTER_NAME, value=1),
    )
    conn.commit()


def read_counter(conn: Connection) -> int:
    (value,) = conn.execute(
        "SELECT value FROM counter WHERE name = %s", [COUNTER_NAME]
    ).fetchone()
    return value


def update_counter(conn: Connection, value: int) -> int:
    (value,) = conn.execute(
        "UPDATE counter SET value = %(value)s WHERE name = %(name)s RETURNING value",
        dict(value=value, name=COUNTER_NAME),
    ).fetchone()
    return value


c1 = open_connection()
c2 = open_connection()

print(f"setting transaction isolation level to: {str(target_isolation_level)}")
c1.set_isolation_level(target_isolation_level)
c2.set_isolation_level(target_isolation_level)

init_counter(c1)
print(f"initial counter value is {read_counter(c1)}")

print(f"2 transactions are now trying to currently increment the counter")

if args.serial:
    print(
        """
execution is serialized: 

1: T1 reads counter
2: T1 increments counters and commits
3: T2 reads counter
4: T2 increments counters and commits
"""
    )
    value1 = read_counter(c1)
    update_counter(c1, value1 + 1)
    c1.commit()

    value2 = read_counter(c2)
    update_counter(c2, value2 + 1)
    c2.commit()
else:
    print(
        """
execution is interleaved: 

1: T1 reads counter
2: T2 reads counter
3: T1 increments counters and commits
4: T2 increments counters and commits
"""
    )
    value1 = read_counter(c1)
    value2 = read_counter(c2)
    update_counter(c1, value1 + 1)
    c1.commit()
    try:
        update_counter(c2, value2 + 1)
    except Exception as e:
        print(f"T2 could not update counter: {traceback.format_exc(0)}")
    c2.commit()

c3 = open_connection()
value = read_counter(c3)
print(f"final counter value is {value}")
