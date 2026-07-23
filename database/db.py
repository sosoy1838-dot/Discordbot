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
                # Rangválasztó panelek
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS role_panels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL UNIQUE,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                created_by INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # A panelekhez tartozó ranggombok
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS role_panel_buttons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                panel_id INTEGER NOT NULL,
                role_id INTEGER NOT NULL,
                label TEXT NOT NULL,
                emoji TEXT,
                style INTEGER NOT NULL DEFAULT 2,
                position INTEGER NOT NULL DEFAULT 0,

                UNIQUE (panel_id, role_id)
            )
            """
        )

        await db.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_role_panels_guild
            ON role_panels (guild_id)
            """
        )

        await db.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_role_panel_buttons_panel
            ON role_panel_buttons (panel_id)
            """
        )
                # A bot konfigurálására jogosult rangok
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS bot_manager_roles (
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
async def create_role_panel(
    guild_id: int,
    channel_id: int,
    message_id: int,
    title: str,
    description: str,
    created_by: int,
) -> int:
    """
    Létrehoz egy rangválasztó panelt,
    majd visszaadja a panel azonosítóját.
    """

    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            """
            INSERT INTO role_panels (
                guild_id,
                channel_id,
                message_id,
                title,
                description,
                created_by
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                guild_id,
                channel_id,
                message_id,
                title,
                description,
                created_by,
            ),
        )

        await db.commit()

        panel_id = cursor.lastrowid
        await cursor.close()

        if panel_id is None:
            raise RuntimeError(
                "Nem sikerült létrehozni a rangpanelt."
            )

        return panel_id


async def get_role_panel(
    guild_id: int,
    panel_id: int,
) -> dict | None:
    """
    Lekér egy rangpanelt az azonosítója alapján.
    """

    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row

        async with db.execute(
            """
            SELECT
                id,
                guild_id,
                channel_id,
                message_id,
                title,
                description,
                created_by,
                created_at
            FROM role_panels
            WHERE guild_id = ?
              AND id = ?
            """,
            (
                guild_id,
                panel_id,
            ),
        ) as cursor:
            row = await cursor.fetchone()

    if row is None:
        return None

    return dict(row)


async def get_all_role_panels() -> list[dict]:
    """
    Lekéri az összes szerver összes rangpaneljét.
    A bot indulásakor használjuk.
    """

    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row

        async with db.execute(
            """
            SELECT
                id,
                guild_id,
                channel_id,
                message_id,
                title,
                description,
                created_by,
                created_at
            FROM role_panels
            ORDER BY id
            """
        ) as cursor:
            rows = await cursor.fetchall()

    return [dict(row) for row in rows]


async def get_guild_role_panels(
    guild_id: int,
) -> list[dict]:
    """
    Lekéri egy szerver rangpaneljeit.
    """

    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row

        async with db.execute(
            """
            SELECT
                id,
                guild_id,
                channel_id,
                message_id,
                title,
                description,
                created_by,
                created_at
            FROM role_panels
            WHERE guild_id = ?
            ORDER BY id
            """,
            (guild_id,),
        ) as cursor:
            rows = await cursor.fetchall()

    return [dict(row) for row in rows]


async def add_role_panel_button(
    panel_id: int,
    role_id: int,
    label: str,
    emoji: str | None,
    style: int,
) -> bool:
    """
    Rangot ad egy panelhez.

    True: sikerült hozzáadni.
    False: a rang már szerepel a panelen.
    """

    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            """
            SELECT COUNT(*)
            FROM role_panel_buttons
            WHERE panel_id = ?
            """,
            (panel_id,),
        ) as cursor:
            count_row = await cursor.fetchone()

        button_count = int(count_row[0]) if count_row else 0

        if button_count >= 25:
            raise ValueError(
                "Egy panelen legfeljebb 25 ranggomb lehet."
            )

        cursor = await db.execute(
            """
            INSERT OR IGNORE INTO role_panel_buttons (
                panel_id,
                role_id,
                label,
                emoji,
                style,
                position
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                panel_id,
                role_id,
                label,
                emoji,
                style,
                button_count,
            ),
        )

        await db.commit()

        added = cursor.rowcount > 0
        await cursor.close()

        return added


async def get_role_panel_buttons(
    panel_id: int,
) -> list[dict]:
    """
    Lekéri egy rangpanel összes gombját.
    """

    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row

        async with db.execute(
            """
            SELECT
                id,
                panel_id,
                role_id,
                label,
                emoji,
                style,
                position
            FROM role_panel_buttons
            WHERE panel_id = ?
            ORDER BY position, id
            """,
            (panel_id,),
        ) as cursor:
            rows = await cursor.fetchall()

    return [dict(row) for row in rows]


async def remove_role_panel_button(
    panel_id: int,
    role_id: int,
) -> bool:
    """
    Eltávolít egy ranggombot a panelről.
    """

    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            """
            DELETE FROM role_panel_buttons
            WHERE panel_id = ?
              AND role_id = ?
            """,
            (
                panel_id,
                role_id,
            ),
        )

        await db.commit()

        removed = cursor.rowcount > 0
        await cursor.close()

        return removed


async def delete_role_panel(
    guild_id: int,
    panel_id: int,
) -> bool:
    """
    Törli a panel adatbázis-bejegyzését
    és a hozzá tartozó gombokat.
    """

    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            """
            SELECT id
            FROM role_panels
            WHERE guild_id = ?
              AND id = ?
            """,
            (
                guild_id,
                panel_id,
            ),
        ) as cursor:
            row = await cursor.fetchone()

        if row is None:
            return False

        await db.execute(
            """
            DELETE FROM role_panel_buttons
            WHERE panel_id = ?
            """,
            (panel_id,),
        )

        await db.execute(
            """
            DELETE FROM role_panels
            WHERE guild_id = ?
              AND id = ?
            """,
            (
                guild_id,
                panel_id,
            ),
        )

        await db.commit()

        return True
async def add_bot_manager_role(
    guild_id: int,
    role_id: int,
) -> bool:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            """
            INSERT OR IGNORE INTO bot_manager_roles (
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

        # Az async with blokkon BELÜL kell lennie.
        await db.commit()

        added = cursor.rowcount > 0
        await cursor.close()

        return added


async def remove_bot_manager_role(
    guild_id: int,
    role_id: int,
) -> bool:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            """
            DELETE FROM bot_manager_roles
            WHERE guild_id = ?
              AND role_id = ?
            """,
            (
                guild_id,
                role_id,
            ),
        )

        # Az async with blokkon BELÜL kell lennie.
        await db.commit()

        removed = cursor.rowcount > 0
        await cursor.close()

        return removed


async def get_bot_manager_roles(
    guild_id: int,
) -> list[int]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            """
            SELECT role_id
            FROM bot_manager_roles
            WHERE guild_id = ?
            ORDER BY role_id
            """,
            (guild_id,),
        ) as cursor:
            rows = await cursor.fetchall()

    return [int(row[0]) for row in rows]