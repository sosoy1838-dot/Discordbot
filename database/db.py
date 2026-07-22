from pathlib import Path

import aiosqlite


# A projekt főmappája.
BASE_DIR = Path(__file__).resolve().parents[1]

# Az adatbázis helye:
# bot/database.db
DATABASE_PATH = BASE_DIR / "database.db"


async def init_database() -> None:
    """
    Létrehozza az adatbázist és a szükséges táblákat,
    ha még nem léteznek.
    """

    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS warnings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                moderator_id INTEGER NOT NULL,
                reason TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        await db.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_warnings_guild_user
            ON warnings (guild_id, user_id)
            """
        )

        await db.commit()


async def add_warning(
    guild_id: int,
    user_id: int,
    moderator_id: int,
    reason: str,
) -> int:
    """
    Elment egy új figyelmeztetést,
    majd visszaadja annak azonosítóját.
    """

    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            """
            INSERT INTO warnings (
                guild_id,
                user_id,
                moderator_id,
                reason
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                guild_id,
                user_id,
                moderator_id,
                reason,
            ),
        )

        await db.commit()

        warning_id = cursor.lastrowid
        await cursor.close()

        if warning_id is None:
            raise RuntimeError(
                "Nem sikerült létrehozni a figyelmeztetést."
            )

        return warning_id


async def get_warnings(
    guild_id: int,
    user_id: int,
    limit: int = 10,
) -> list[dict]:
    """
    Lekéri egy tag legutóbbi figyelmeztetéseit.
    """

    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row

        async with db.execute(
            """
            SELECT
                id,
                guild_id,
                user_id,
                moderator_id,
                reason,
                created_at
            FROM warnings
            WHERE guild_id = ?
              AND user_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (
                guild_id,
                user_id,
                limit,
            ),
        ) as cursor:
            rows = await cursor.fetchall()

        return [dict(row) for row in rows]


async def count_warnings(
    guild_id: int,
    user_id: int,
) -> int:
    """
    Megszámolja egy tag összes figyelmeztetését.
    """

    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            """
            SELECT COUNT(*)
            FROM warnings
            WHERE guild_id = ?
              AND user_id = ?
            """,
            (
                guild_id,
                user_id,
            ),
        ) as cursor:
            row = await cursor.fetchone()

        if row is None:
            return 0

        return int(row[0])


async def delete_warning(
    guild_id: int,
    warning_id: int,
) -> dict | None:
    """
    Töröl egy figyelmeztetést.

    Ha nem található, None értéket ad vissza.
    """

    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row

        async with db.execute(
            """
            SELECT
                id,
                guild_id,
                user_id,
                moderator_id,
                reason,
                created_at
            FROM warnings
            WHERE guild_id = ?
              AND id = ?
            """,
            (
                guild_id,
                warning_id,
            ),
        ) as cursor:
            row = await cursor.fetchone()

        if row is None:
            return None

        await db.execute(
            """
            DELETE FROM warnings
            WHERE guild_id = ?
              AND id = ?
            """,
            (
                guild_id,
                warning_id,
            ),
        )

        await db.commit()

        return dict(row)