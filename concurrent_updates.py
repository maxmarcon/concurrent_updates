#! /usr/bin/env python

import traceback
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, Connection
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
    "ru": "READ UNCOMMITTED",
    "rc": "READ COMMITTED",
    "rr": "REPEATABLE READ",
    "s": "SERIALIZABLE",
}


target_isolation_level = isolation_level_map[args.isolation_level]

COUNTER_NAME = "a"

engine = create_engine(
    "postgresql+psycopg://postgres:postgres@localhost/postgres",
    isolation_level=target_isolation_level,
)


def open_connection(engine: Engine) -> Connection:
    return engine.connect()


def init_counter(conn: Connection):
    conn.execute(
        text("CREATE TABLE IF NOT EXISTS counter (name text primary key, value int)")
    )
    conn.execute(
        text(
            "INSERT INTO counter VALUES (:name, :value) ON CONFLICT ON CONSTRAINT counter_pkey DO UPDATE SET value = :value"
        ),
        dict(name=COUNTER_NAME, value=1),
    )
    conn.commit()


def read_counter(conn: Connection) -> int:
    (value,) = conn.execute(
        text("SELECT value FROM counter WHERE name = :name"), dict(name=COUNTER_NAME)
    ).fetchone()
    return value


def update_counter(conn: Connection, value: int) -> int:
    (value,) = conn.execute(
        text("UPDATE counter SET value = :value WHERE name = :name RETURNING value"),
        dict(value=value, name=COUNTER_NAME),
    ).fetchone()
    return value


c1 = open_connection(engine)
c2 = open_connection(engine)

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

c3 = open_connection(engine)
value = read_counter(c3)
print(f"final counter value is {value}")
