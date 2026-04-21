"""
Dialect-agnostic upsert — works with both PostgreSQL and SQLite.
Uses index_elements (not named constraints) so SQLite 3.24+ is compatible.
SQLite limit: 999 bind variables → auto-chunks large batches.
"""
from typing import Any

_SQLITE_VAR_LIMIT = 999


def upsert(session, table, records: list[dict[str, Any]],
           index_elements: list[str], update_cols: list[str]) -> int:
    """INSERT ... ON CONFLICT DO UPDATE for any SQLAlchemy dialect."""
    if not records:
        return 0

    dialect = session.bind.dialect.name

    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as _insert
        return _do_upsert(session, table, records, index_elements, update_cols, _insert)
    else:
        from sqlalchemy.dialects.sqlite import insert as _insert  # type: ignore
        # SQLite caps bind variables at 999; chunk to stay under limit
        n_cols = len(records[0])
        chunk_size = max(1, _SQLITE_VAR_LIMIT // n_cols)
        total = 0
        for i in range(0, len(records), chunk_size):
            total += _do_upsert(
                session, table, records[i:i + chunk_size],
                index_elements, update_cols, _insert,
            )
        return total


def _do_upsert(session, table, records, index_elements, update_cols, _insert) -> int:
    stmt = _insert(table).values(records)
    update_dict = {col: getattr(stmt.excluded, col) for col in update_cols}
    stmt = stmt.on_conflict_do_update(index_elements=index_elements, set_=update_dict)
    result = session.execute(stmt)
    session.commit()
    return result.rowcount
