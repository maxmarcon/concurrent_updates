# Concurrent updates

This program simulates 2 concurrent transactions that try to increment the same counter (initialized with 1) in a postgres table under 
a given [isolation level](https://www.postgresql.org/docs/current/transaction-iso.html).

## Setup

1. Install packages: `pip install -r requirements.txt`
2. Start a postgres database with the following command: `docker run  --rm -e POSTGRES_PASSWORD=postgres -p 5432:5432 postgres`

## Usage

```
usage: concurrent_updates.py [-h] [--serial] {ru,rc,rr,s}

positional arguments:
  {ru,rc,rr,s}  isolation level: ru (read uncomitted) rc (read committed) rr
                (repeatable reads) s (serializable)

options:
  -h, --help    show this help message and exit
  --serial, -s  whether to serialize transaction execution or interleave them.
                Serialized execution will never cause a serialization error

```

## Explanation

When the command is run with the `--serial` flag, these operations will be performed on the counter, in this order:

1. T1 reads counter
1. T1 increments counters and commits
1. T2 reads counter
1. T2 increments counters and commits

This causes no serialization errors, and the final value of the counter is the correct one (3) under any isolation level.

When the command is run withotu the `--serial` flag, the operations in the following order:

1: T1 reads counter
1: T2 reads counter
1: T1 increments counters and commits
1: T2 increments counters and commits

And this will result in the following behavior depending on the isolation level:

| Isolation level      | DB exception                         | Final counter value |
|----------------------|--------------------------------------|---------------------|
| **Read uncommitted** | None                                 | 2 (wrong)           |
| **Read committed**   | None                                 | 2 (wrong)           |
| **Repeatable read**  | T2 aborted with SerializationFailure | 2 (correct)         |
| **Serializable**     | T2 aborted with SerializationFailure | 2 (correct)         |

As you can see, under the `Read uncommitted` and `Read committed` isolation levels, the invalid sequence of operation
resulting in the wrong result (final counter value 2 instead of 3) is let go through.
On the other hand, under the `Repeatable read` and `Serializable` isolation levels, the invalid sequence of operation triggers
a `SerializationFailure` error when T2 tries to update the counter - T2 is aborted and the final counter value (although still 2) is correct, because only T1 has committed and incremented the counter.