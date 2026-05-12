import aiosqlite
from structures import LLM, MCP, Message, Author

DB_NAME = 'api_agent.db'


async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT
            );

            CREATE TABLE IF NOT EXISTS llm_configs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                base_url TEXT,
                api_key TEXT,
                model TEXT
            );

            CREATE TABLE IF NOT EXISTS mcp_configs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                url TEXT,
                token TEXT,
                name TEXT
            );

            CREATE TABLE IF NOT EXISTS chats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                llm_config_id INTEGER
            );

            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER,
                author TEXT,
                content TEXT,
                date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS chat_mcp_links (
                chat_id INTEGER,
                mcp_config_id INTEGER
            );
        """)

        await db.execute(
            "INSERT INTO mcp_configs (user_id, url, token, name) SELECT 0, 'local', 'none', 'Встроенные мат. тулы' WHERE NOT EXISTS (SELECT 1 FROM mcp_configs WHERE url = 'local')"
        )

        await db.commit()


async def get_user_id_by_username(username: str):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT id FROM users WHERE username = ?",
            (username,)
        ) as cursor:
            user_id = await cursor.fetchone()
            return user_id[0] if user_id else None


async def get_user_id_by_chat_id(chat_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT user_id FROM chats WHERE id = ?",
            (chat_id,)
        ) as cursor:
            user_id = await cursor.fetchone()
            return user_id[0] if user_id else None


async def add_user_if_not_exist(username: str):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT id FROM users WHERE username = ?",
            (username,)
        ) as cursor:
            user_id = await cursor.fetchone()
            if not user_id:
                await db.execute(
                    "INSERT INTO users (username) VALUES (?)",
                    (username,)
                )
                await db.commit()

async def check_user_chat(username: str, chat_id: int):
    if await get_user_id_by_username(username) != await get_user_id_by_chat_id(chat_id):
        raise PermissionError("У вас нет доступа к этому чату")


async def add_llm_local(llm_config: LLM, username: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT INTO llm_configs (user_id, base_url, api_key, model) VALUES (?, ?, ?, ?)",
            (await get_user_id_by_username(username), llm_config.base_url, llm_config.api_key, llm_config.model)
        )
        await db.commit()


async def get_llm_local(username: str):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT id, base_url, api_key, model FROM llm_configs WHERE user_id = ?",
            (await get_user_id_by_username(username),)
        ) as cursor:
            llm_config_ids = await cursor.fetchall()
            return [{"id": llm[0], "url": llm[1], "token": llm[2], "name": llm[3]} for llm in llm_config_ids]


async def add_mcp_local(mcp: MCP, username: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT INTO mcp_configs (user_id, url, token, name) VALUES (?, ?, ?, ?)",
            (await get_user_id_by_username(username), mcp.url, mcp.token, mcp.name)
        )
        await db.commit()


async def get_mcp_local(username: str):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT id, url, token, name FROM mcp_configs WHERE user_id = ? OR user_id = 0",
            (await get_user_id_by_username(username),)
        ) as cursor:
            mcp_config_ids = await cursor.fetchall()
            return [{"id": mcp[0], "url": mcp[1], "token": mcp[2], "name": mcp[3]} for mcp in mcp_config_ids]


async def activate_mcp_local(chat_id: int, mcp_config_id: int, username: str):
    await check_user_chat(username, chat_id)

    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT id FROM mcp_configs WHERE (user_id = ? OR user_id = 0) and id = ?",
            (await get_user_id_by_username(username), mcp_config_id)
        ) as cursor:
            check = await cursor.fetchone()
            if not check:
                raise ValueError("MCP-конфиг не найден или вам не принадлежит")

        await db.execute(
            "INSERT INTO chat_mcp_links (chat_id, mcp_config_id) VALUES (?, ?)",
            (chat_id, mcp_config_id)
        )
        await db.commit()


async def deactivate_mcp_local(chat_id: int, mcp_config_id: int, username: str):
    await check_user_chat(username, chat_id)

    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT id FROM mcp_configs WHERE (user_id = ? OR user_id = 0) and id = ?",
            (await get_user_id_by_username(username), mcp_config_id)
        ) as cursor:
            check = await cursor.fetchone()
            if not check:
                raise ValueError("MCP-конфиг не найден или вам не принадлежит")

        await db.execute(
            "DELETE FROM chat_mcp_links WHERE chat_id = ? and mcp_config_id = ?",
            (chat_id, mcp_config_id)
        )
        await db.commit()


async def add_chat_local(llm_config_id: int, username: str):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT id FROM llm_configs WHERE user_id = ? and id = ?",
            (await get_user_id_by_username(username), llm_config_id)
        ) as cursor:
            check = await cursor.fetchone()
            if not check:
                raise ValueError("LLM-конфиг не найден или вам не принадлежит")

        await db.execute(
            "INSERT INTO chats (user_id, llm_config_id) VALUES (?, ?)",
            (await get_user_id_by_username(username), llm_config_id)
        )
        await db.commit()


async def get_all_chats_local(username: str):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT id, llm_config_id FROM chats WHERE user_id = ?",
            (await get_user_id_by_username(username),)
        ) as cursor:
            chat_config_ids = await cursor.fetchall()
            return [{"id": chat[0], "llm_config_id": chat[1]} for chat in chat_config_ids]


async def add_message_local(chat_id: int, author: Author, message: Message, isLlm: bool):
    if not isLlm:
        await check_user_chat(author.name, chat_id)

    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT INTO messages (chat_id, author, content) VALUES (?, ?, ?)",
            (chat_id, author.name, message.text)
        )
        await db.commit()


async def read_chat_history_local(chat_id: int, username: str):
    await check_user_chat(username, chat_id)

    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT author, content, date FROM messages WHERE chat_id = ? ORDER BY date ASC",
            (chat_id,)
        ) as cursor:
            messages = await cursor.fetchall()
            return [{"author": m[0], "content": m[1], "date": m[2]} for m in messages] if messages else []


async def get_all_mcp_by_chat_id(chat_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            """
            SELECT m.url, m.token, m.name 
            FROM mcp_configs m
            JOIN chat_mcp_links l ON m.id = l.mcp_config_id
            WHERE l.chat_id = ?
            """,
            (chat_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [{"url": r[0], "token": r[1], "name": r[2]} for r in rows]

async def get_llm_config_by_chat_id(chat_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            """
            SELECT l.base_url, l.api_key, l.model 
            FROM llm_configs l
            JOIN chats c ON l.id = c.llm_config_id
            WHERE c.id = ?
            """,
            (chat_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return {"base_url": row[0], "api_key": row[1], "model": row[2]}
            return None
