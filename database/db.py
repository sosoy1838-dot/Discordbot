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
                # Ticketek
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL UNIQUE,
                opener_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',
                claimed_by INTEGER,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                closed_at TEXT
            )
            """
        )

        await db.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_tickets_guild_opener_status
            ON tickets (
                guild_id,
                opener_id,
                status
            )
            """
        )

        await db.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_tickets_channel
            ON tickets (channel_id)
            """
        )
                # Staff-ping védelem alól kivételes rangok
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS staff_ping_exempt_roles (
                guild_id INTEGER NOT NULL,
                role_id INTEGER NOT NULL,

                PRIMARY KEY (guild_id, role_id)
            )
            """
        )

        # Staff-ping védelem alól kivételes csatornák
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS staff_ping_exempt_channels (
                guild_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,

                PRIMARY KEY (guild_id, channel_id)
            )
            """
        )

                # Linkvédelem: korlátozott rangok
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS link_protect_restricted_roles (
                guild_id INTEGER NOT NULL,
                role_id INTEGER NOT NULL,
                PRIMARY KEY (guild_id, role_id)
            )
            """
        )

        # Linkvédelem: kivételes rangok
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS link_protect_exempt_roles (
                guild_id INTEGER NOT NULL,
                role_id INTEGER NOT NULL,
                PRIMARY KEY (guild_id, role_id)
            )
            """
        )

        # Linkvédelem: kivételes csatornák
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS link_protect_exempt_channels (
                guild_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                PRIMARY KEY (guild_id, channel_id)
            )
            """
        )

        # Linkvédelem: engedélyezett domainek
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS link_protect_allowed_domains (
                guild_id INTEGER NOT NULL,
                domain TEXT NOT NULL COLLATE NOCASE,
                PRIMARY KEY (guild_id, domain)
            )
            """
        )
                # Giveawayek
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS giveaways (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                message_id INTEGER UNIQUE,
                host_id INTEGER NOT NULL,
                prize TEXT NOT NULL,
                winner_count INTEGER NOT NULL DEFAULT 1,
                end_time TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                ended_at TEXT
            )
            """
        )

        # Giveaway jelentkezők
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS giveaway_entries (
                giveaway_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                joined_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

                PRIMARY KEY (giveaway_id, user_id),

                FOREIGN KEY (giveaway_id)
                    REFERENCES giveaways(id)
                    ON DELETE CASCADE
            )
            """
        )

        await db.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_giveaways_status_end_time
            ON giveaways (status, end_time)
            """
        )
                # Automoderáció alól kivételes rangok
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS automod_exempt_roles (
                guild_id INTEGER NOT NULL,
                role_id INTEGER NOT NULL,

                PRIMARY KEY (guild_id, role_id)
            )
            """
        )

        # Automoderáció alól kivételes csatornák
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS automod_exempt_channels (
                guild_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,

                PRIMARY KEY (guild_id, channel_id)
            )
            """
        )

        # Tiltott szavak
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS automod_blocked_words (
                guild_id INTEGER NOT NULL,
                word TEXT NOT NULL COLLATE NOCASE,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

                PRIMARY KEY (guild_id, word)
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
async def create_ticket(
    guild_id: int,
    channel_id: int,
    opener_id: int,
) -> int:
    """
    Elment egy új ticketet, és visszaadja
    az adatbázisbeli ticketazonosítót.
    """

    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            """
            INSERT INTO tickets (
                guild_id,
                channel_id,
                opener_id,
                status
            )
            VALUES (?, ?, ?, 'open')
            """,
            (
                guild_id,
                channel_id,
                opener_id,
            ),
        )

        await db.commit()

        ticket_id = cursor.lastrowid
        await cursor.close()

        if ticket_id is None:
            raise RuntimeError(
                "Nem sikerült elmenteni a ticketet."
            )

        return ticket_id


async def get_open_ticket_for_user(
    guild_id: int,
    opener_id: int,
) -> dict | None:
    """
    Megkeresi a felhasználó jelenleg nyitott ticketjét.
    """

    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row

        async with db.execute(
            """
            SELECT
                id,
                guild_id,
                channel_id,
                opener_id,
                status,
                claimed_by,
                created_at,
                closed_at
            FROM tickets
            WHERE guild_id = ?
              AND opener_id = ?
              AND status = 'open'
            ORDER BY id DESC
            LIMIT 1
            """,
            (
                guild_id,
                opener_id,
            ),
        ) as cursor:
            row = await cursor.fetchone()

    if row is None:
        return None

    return dict(row)


async def get_ticket_by_channel(
    channel_id: int,
) -> dict | None:
    """
    Lekéri a ticketet a Discord-csatornája alapján.
    """

    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row

        async with db.execute(
            """
            SELECT
                id,
                guild_id,
                channel_id,
                opener_id,
                status,
                claimed_by,
                created_at,
                closed_at
            FROM tickets
            WHERE channel_id = ?
            LIMIT 1
            """,
            (channel_id,),
        ) as cursor:
            row = await cursor.fetchone()

    if row is None:
        return None

    return dict(row)


async def claim_ticket(
    channel_id: int,
    staff_id: int,
) -> bool:
    """
    Egy stafftaghoz rendeli a ticketet.

    Csak akkor sikerül, ha a ticket nyitott,
    és még senki nem claimelte.
    """

    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            """
            UPDATE tickets
            SET claimed_by = ?
            WHERE channel_id = ?
              AND status = 'open'
              AND claimed_by IS NULL
            """,
            (
                staff_id,
                channel_id,
            ),
        )

        await db.commit()

        updated = cursor.rowcount > 0
        await cursor.close()

        return updated


async def close_ticket(
    channel_id: int,
) -> bool:
    """
    Lezártként jelöli meg a ticketet.
    """

    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            """
            UPDATE tickets
            SET
                status = 'closed',
                closed_at = CURRENT_TIMESTAMP
            WHERE channel_id = ?
              AND status = 'open'
            """,
            (channel_id,),
        )

        await db.commit()

        updated = cursor.rowcount > 0
        await cursor.close()

        return updated
async def add_staff_ping_exempt_role(
    guild_id: int,
    role_id: int,
) -> bool:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            """
            INSERT OR IGNORE INTO staff_ping_exempt_roles (
                guild_id,
                role_id
            )
            VALUES (?, ?)
            """,
            (guild_id, role_id),
        )

        await db.commit()

        added = cursor.rowcount > 0
        await cursor.close()

        return added


async def remove_staff_ping_exempt_role(
    guild_id: int,
    role_id: int,
) -> bool:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            """
            DELETE FROM staff_ping_exempt_roles
            WHERE guild_id = ?
              AND role_id = ?
            """,
            (guild_id, role_id),
        )

        await db.commit()

        removed = cursor.rowcount > 0
        await cursor.close()

        return removed


async def get_staff_ping_exempt_roles(
    guild_id: int,
) -> list[int]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            """
            SELECT role_id
            FROM staff_ping_exempt_roles
            WHERE guild_id = ?
            ORDER BY role_id
            """,
            (guild_id,),
        ) as cursor:
            rows = await cursor.fetchall()

    return [int(row[0]) for row in rows]


async def add_staff_ping_exempt_channel(
    guild_id: int,
    channel_id: int,
) -> bool:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            """
            INSERT OR IGNORE INTO staff_ping_exempt_channels (
                guild_id,
                channel_id
            )
            VALUES (?, ?)
            """,
            (guild_id, channel_id),
        )

        await db.commit()

        added = cursor.rowcount > 0
        await cursor.close()

        return added


async def remove_staff_ping_exempt_channel(
    guild_id: int,
    channel_id: int,
) -> bool:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            """
            DELETE FROM staff_ping_exempt_channels
            WHERE guild_id = ?
              AND channel_id = ?
            """,
            (guild_id, channel_id),
        )

        await db.commit()

        removed = cursor.rowcount > 0
        await cursor.close()

        return removed


async def get_staff_ping_exempt_channels(
    guild_id: int,
) -> list[int]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            """
            SELECT channel_id
            FROM staff_ping_exempt_channels
            WHERE guild_id = ?
            ORDER BY channel_id
            """,
            (guild_id,),
        ) as cursor:
            rows = await cursor.fetchall()

    return [int(row[0]) for row in rows]
# ======================================================
# Linkvédelem adatbázis-függvényei
# ======================================================


async def _add_link_protect_id(
    table_name: str,
    column_name: str,
    guild_id: int,
    value: int,
) -> bool:
    """
    Belső segédfüggvény rang vagy csatorna hozzáadásához.

    A table_name és column_name értékeket csak a lentebbi
    belső függvények használják, nem Discord-felhasználók.
    """

    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            f"""
            INSERT OR IGNORE INTO {table_name} (
                guild_id,
                {column_name}
            )
            VALUES (?, ?)
            """,
            (guild_id, value),
        )

        await db.commit()

        added = cursor.rowcount > 0
        await cursor.close()

        return added


async def _remove_link_protect_id(
    table_name: str,
    column_name: str,
    guild_id: int,
    value: int,
) -> bool:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            f"""
            DELETE FROM {table_name}
            WHERE guild_id = ?
              AND {column_name} = ?
            """,
            (guild_id, value),
        )

        await db.commit()

        removed = cursor.rowcount > 0
        await cursor.close()

        return removed


async def _get_link_protect_ids(
    table_name: str,
    column_name: str,
    guild_id: int,
) -> list[int]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            f"""
            SELECT {column_name}
            FROM {table_name}
            WHERE guild_id = ?
            ORDER BY {column_name}
            """,
            (guild_id,),
        ) as cursor:
            rows = await cursor.fetchall()

    return [int(row[0]) for row in rows]


# ------------------------------------------------------
# Korlátozott rangok
# ------------------------------------------------------


async def add_link_protect_restricted_role(
    guild_id: int,
    role_id: int,
) -> bool:
    return await _add_link_protect_id(
        "link_protect_restricted_roles",
        "role_id",
        guild_id,
        role_id,
    )


async def remove_link_protect_restricted_role(
    guild_id: int,
    role_id: int,
) -> bool:
    return await _remove_link_protect_id(
        "link_protect_restricted_roles",
        "role_id",
        guild_id,
        role_id,
    )


async def get_link_protect_restricted_roles(
    guild_id: int,
) -> list[int]:
    return await _get_link_protect_ids(
        "link_protect_restricted_roles",
        "role_id",
        guild_id,
    )


# ------------------------------------------------------
# Kivételes rangok
# ------------------------------------------------------


async def add_link_protect_exempt_role(
    guild_id: int,
    role_id: int,
) -> bool:
    return await _add_link_protect_id(
        "link_protect_exempt_roles",
        "role_id",
        guild_id,
        role_id,
    )


async def remove_link_protect_exempt_role(
    guild_id: int,
    role_id: int,
) -> bool:
    return await _remove_link_protect_id(
        "link_protect_exempt_roles",
        "role_id",
        guild_id,
        role_id,
    )


async def get_link_protect_exempt_roles(
    guild_id: int,
) -> list[int]:
    return await _get_link_protect_ids(
        "link_protect_exempt_roles",
        "role_id",
        guild_id,
    )


# ------------------------------------------------------
# Kivételes csatornák
# ------------------------------------------------------


async def add_link_protect_exempt_channel(
    guild_id: int,
    channel_id: int,
) -> bool:
    return await _add_link_protect_id(
        "link_protect_exempt_channels",
        "channel_id",
        guild_id,
        channel_id,
    )


async def remove_link_protect_exempt_channel(
    guild_id: int,
    channel_id: int,
) -> bool:
    return await _remove_link_protect_id(
        "link_protect_exempt_channels",
        "channel_id",
        guild_id,
        channel_id,
    )


async def get_link_protect_exempt_channels(
    guild_id: int,
) -> list[int]:
    return await _get_link_protect_ids(
        "link_protect_exempt_channels",
        "channel_id",
        guild_id,
    )


# ------------------------------------------------------
# Engedélyezett domainek
# ------------------------------------------------------


async def add_link_protect_allowed_domain(
    guild_id: int,
    domain: str,
) -> bool:
    normalized_domain = domain.strip().lower()

    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            """
            INSERT OR IGNORE INTO link_protect_allowed_domains (
                guild_id,
                domain
            )
            VALUES (?, ?)
            """,
            (
                guild_id,
                normalized_domain,
            ),
        )

        await db.commit()

        added = cursor.rowcount > 0
        await cursor.close()

        return added


async def remove_link_protect_allowed_domain(
    guild_id: int,
    domain: str,
) -> bool:
    normalized_domain = domain.strip().lower()

    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            """
            DELETE FROM link_protect_allowed_domains
            WHERE guild_id = ?
              AND domain = ?
            """,
            (
                guild_id,
                normalized_domain,
            ),
        )

        await db.commit()

        removed = cursor.rowcount > 0
        await cursor.close()

        return removed


async def get_link_protect_allowed_domains(
    guild_id: int,
) -> list[str]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            """
            SELECT domain
            FROM link_protect_allowed_domains
            WHERE guild_id = ?
            ORDER BY domain
            """,
            (guild_id,),
        ) as cursor:
            rows = await cursor.fetchall()

    return [str(row[0]) for row in rows]
# ======================================================
# Giveaway adatbázis-függvények
# ======================================================


async def create_giveaway(
    guild_id: int,
    channel_id: int,
    host_id: int,
    prize: str,
    winner_count: int,
    end_time: str,
) -> int:
    """
    Új giveaway létrehozása.

    Az end_time UTC időpont ISO formátumban.
    """

    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            """
            INSERT INTO giveaways (
                guild_id,
                channel_id,
                host_id,
                prize,
                winner_count,
                end_time,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, 'active')
            """,
            (
                guild_id,
                channel_id,
                host_id,
                prize,
                winner_count,
                end_time,
            ),
        )

        await db.commit()

        giveaway_id = cursor.lastrowid
        await cursor.close()

        if giveaway_id is None:
            raise RuntimeError(
                "Nem sikerült létrehozni a giveawayt."
            )

        return int(giveaway_id)


async def set_giveaway_message_id(
    giveaway_id: int,
    message_id: int,
) -> bool:
    """
    Elmenti a giveaway Discord-üzenetének azonosítóját.
    """

    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            """
            UPDATE giveaways
            SET message_id = ?
            WHERE id = ?
            """,
            (
                message_id,
                giveaway_id,
            ),
        )

        await db.commit()

        updated = cursor.rowcount > 0
        await cursor.close()

        return updated


async def get_giveaway_by_id(
    giveaway_id: int,
) -> dict | None:
    """
    Giveaway lekérése a belső azonosító alapján.
    """

    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row

        async with db.execute(
            """
            SELECT *
            FROM giveaways
            WHERE id = ?
            """,
            (giveaway_id,),
        ) as cursor:
            row = await cursor.fetchone()

    if row is None:
        return None

    return dict(row)


async def get_giveaway_by_message(
    message_id: int,
) -> dict | None:
    """
    Giveaway lekérése a Discord-üzenet azonosítója alapján.
    """

    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row

        async with db.execute(
            """
            SELECT *
            FROM giveaways
            WHERE message_id = ?
            """,
            (message_id,),
        ) as cursor:
            row = await cursor.fetchone()

    if row is None:
        return None

    return dict(row)


async def get_active_giveaways() -> list[dict]:
    """
    Az összes aktív giveaway lekérése.

    Erre újraindítás után lesz szükség az időzítők
    visszatöltéséhez.
    """

    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row

        async with db.execute(
            """
            SELECT *
            FROM giveaways
            WHERE status = 'active'
            ORDER BY end_time
            """
        ) as cursor:
            rows = await cursor.fetchall()

    return [
        dict(row)
        for row in rows
    ]


async def add_giveaway_entry(
    giveaway_id: int,
    user_id: int,
) -> bool:
    """
    Felhasználó hozzáadása a jelentkezőkhöz.

    False érték érkezik vissza, ha már jelentkezett.
    """

    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            """
            INSERT OR IGNORE INTO giveaway_entries (
                giveaway_id,
                user_id
            )
            VALUES (?, ?)
            """,
            (
                giveaway_id,
                user_id,
            ),
        )

        await db.commit()

        added = cursor.rowcount > 0
        await cursor.close()

        return added


async def remove_giveaway_entry(
    giveaway_id: int,
    user_id: int,
) -> bool:
    """
    Felhasználó jelentkezésének visszavonása.
    """

    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            """
            DELETE FROM giveaway_entries
            WHERE giveaway_id = ?
              AND user_id = ?
            """,
            (
                giveaway_id,
                user_id,
            ),
        )

        await db.commit()

        removed = cursor.rowcount > 0
        await cursor.close()

        return removed


async def get_giveaway_entries(
    giveaway_id: int,
) -> list[int]:
    """
    Giveaway jelentkezőinek felhasználóazonosítói.
    """

    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            """
            SELECT user_id
            FROM giveaway_entries
            WHERE giveaway_id = ?
            ORDER BY joined_at
            """,
            (giveaway_id,),
        ) as cursor:
            rows = await cursor.fetchall()

    return [
        int(row[0])
        for row in rows
    ]


async def count_giveaway_entries(
    giveaway_id: int,
) -> int:
    """
    Megszámolja a giveaway jelentkezőit.
    """

    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            """
            SELECT COUNT(*)
            FROM giveaway_entries
            WHERE giveaway_id = ?
            """,
            (giveaway_id,),
        ) as cursor:
            row = await cursor.fetchone()

    if row is None:
        return 0

    return int(row[0])


async def end_giveaway(
    giveaway_id: int,
) -> bool:
    """
    Aktív giveaway lezárása.
    """

    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            """
            UPDATE giveaways
            SET status = 'ended',
                ended_at = CURRENT_TIMESTAMP
            WHERE id = ?
              AND status = 'active'
            """,
            (giveaway_id,),
        )

        await db.commit()

        updated = cursor.rowcount > 0
        await cursor.close()

        return updated
    # ======================================================
# Automoderáció adatbázis-függvények
# ======================================================


# ------------------------------------------------------
# Kivételes rangok
# ------------------------------------------------------


async def add_automod_exempt_role(
    guild_id: int,
    role_id: int,
) -> bool:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            """
            INSERT OR IGNORE INTO automod_exempt_roles (
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


async def remove_automod_exempt_role(
    guild_id: int,
    role_id: int,
) -> bool:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            """
            DELETE FROM automod_exempt_roles
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


async def get_automod_exempt_roles(
    guild_id: int,
) -> list[int]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            """
            SELECT role_id
            FROM automod_exempt_roles
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


# ------------------------------------------------------
# Kivételes csatornák
# ------------------------------------------------------


async def add_automod_exempt_channel(
    guild_id: int,
    channel_id: int,
) -> bool:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            """
            INSERT OR IGNORE INTO automod_exempt_channels (
                guild_id,
                channel_id
            )
            VALUES (?, ?)
            """,
            (
                guild_id,
                channel_id,
            ),
        )

        await db.commit()

        added = cursor.rowcount > 0
        await cursor.close()

        return added


async def remove_automod_exempt_channel(
    guild_id: int,
    channel_id: int,
) -> bool:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            """
            DELETE FROM automod_exempt_channels
            WHERE guild_id = ?
              AND channel_id = ?
            """,
            (
                guild_id,
                channel_id,
            ),
        )

        await db.commit()

        removed = cursor.rowcount > 0
        await cursor.close()

        return removed


async def get_automod_exempt_channels(
    guild_id: int,
) -> list[int]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            """
            SELECT channel_id
            FROM automod_exempt_channels
            WHERE guild_id = ?
            ORDER BY channel_id
            """,
            (guild_id,),
        ) as cursor:
            rows = await cursor.fetchall()

    return [
        int(row[0])
        for row in rows
    ]


# ------------------------------------------------------
# Tiltott szavak
# ------------------------------------------------------


async def add_automod_blocked_word(
    guild_id: int,
    word: str,
) -> bool:
    normalized_word = word.strip().casefold()

    if not normalized_word:
        return False

    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            """
            INSERT OR IGNORE INTO automod_blocked_words (
                guild_id,
                word
            )
            VALUES (?, ?)
            """,
            (
                guild_id,
                normalized_word,
            ),
        )

        await db.commit()

        added = cursor.rowcount > 0
        await cursor.close()

        return added


async def remove_automod_blocked_word(
    guild_id: int,
    word: str,
) -> bool:
    normalized_word = word.strip().casefold()

    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            """
            DELETE FROM automod_blocked_words
            WHERE guild_id = ?
              AND word = ?
            """,
            (
                guild_id,
                normalized_word,
            ),
        )

        await db.commit()

        removed = cursor.rowcount > 0
        await cursor.close()

        return removed


async def get_automod_blocked_words(
    guild_id: int,
) -> list[str]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            """
            SELECT word
            FROM automod_blocked_words
            WHERE guild_id = ?
            ORDER BY word
            """,
            (guild_id,),
        ) as cursor:
            rows = await cursor.fetchall()

    return [
        str(row[0])
        for row in rows
    ]