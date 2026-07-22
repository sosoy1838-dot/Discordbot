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
        # Figyelmeztetések
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

        # Általános szerverbeállítások
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS guild_settings (
                guild_id INTEGER NOT NULL,
                setting_key TEXT NOT NULL,
                setting_value TEXT NOT NULL,

                PRIMARY KEY (guild_id, setting_key)
            )
            """
        )

        # Staffként kezelt Discord-rangok
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS staff_roles (
                guild_id INTEGER NOT NULL,
                role_id INTEGER NOT NULL,

                PRIMARY KEY (guild_id, role_id)
            )
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
async def set_guild_setting(
    guild_id: int,
    setting_key: str,
    setting_value: str | None,
) -> None:
    """
    Elment vagy töröl egy szerverbeállítást.
    """

    async with aiosqlite.connect(DATABASE_PATH) as db:
        if setting_value is None:
            await db.execute(
                """
                DELETE FROM guild_settings
                WHERE guild_id = ?
                  AND setting_key = ?
                """,
                (
                    guild_id,
                    setting_key,
                ),
            )
        else:
            await db.execute(
                """
                INSERT INTO guild_settings (
                    guild_id,
                    setting_key,
                    setting_value
                )
                VALUES (?, ?, ?)
                ON CONFLICT (guild_id, setting_key)
                DO UPDATE SET
                    setting_value = excluded.setting_value
                """,
                (
                    guild_id,
                    setting_key,
                    setting_value,
                ),
            )

        # Ennek az async with blokkon BELÜL kell lennie.
        await db.commit()


async def get_guild_setting(
    guild_id: int,
    setting_key: str,
) -> str | None:
    """
    Lekér egyetlen szerverbeállítást.
    """

    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            """
            SELECT setting_value
            FROM guild_settings
            WHERE guild_id = ?
              AND setting_key = ?
            """,
            (
                guild_id,
                setting_key,
            ),
        ) as cursor:
            row = await cursor.fetchone()

        if row is None:
            return None

        return str(row[0])


async def get_guild_settings(
    guild_id: int,
) -> dict[str, str]:
    """
    Lekéri a szerver összes általános beállítását.
    """

    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            """
            SELECT setting_key, setting_value
            FROM guild_settings
            WHERE guild_id = ?
            """,
            (guild_id,),
        ) as cursor:
            rows = await cursor.fetchall()

    return {
        str(row[0]): str(row[1])
        for row in rows
    }


async def add_staff_role(
    guild_id: int,
    role_id: int,
) -> bool:
    """
    Staffrangot ad a szerver beállításaihoz.

    True: új rang került be.
    False: már korábban is szerepelt.
    """

    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            """
            INSERT OR IGNORE INTO staff_roles (
                guild_id,
                role_id
            )
            VALUES (?, ?)
            """,
            (
                guild_id,
                role_id,
            ),
        )

        await db.commit()

        added = cursor.rowcount > 0
        await cursor.close()

        return added


async def remove_staff_role(
    guild_id: int,
    role_id: int,
) -> bool:
    """
    Eltávolít egy staffrangot.

    True: sikerült törölni.
    False: nem volt beállítva.
    """

    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            """
            DELETE FROM staff_roles
            WHERE guild_id = ?
              AND role_id = ?
            """,
            (
                guild_id,
                role_id,
            ),
        )

        await db.commit()

        removed = cursor.rowcount > 0
        await cursor.close()

        return removed


async def get_staff_roles(
    guild_id: int,
) -> list[int]:
    """
    Lekéri a szerver staffrangjainak azonosítóit.
    """

    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            """
            SELECT role_id
            FROM staff_roles
            WHERE guild_id = ?
            ORDER BY role_id
            """,
            (guild_id,),
        ) as cursor:
            rows = await cursor.fetchall()

    return [
        int(row[0])
        for row in rows
    ]