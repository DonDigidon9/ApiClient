from fastmcp import FastMCP
from mcp import ClientSession
from mcp.client.sse import sse_client

mcp = FastMCP("API-Client-Server")

@mcp.tool()
def multiply_by_two(x: int) -> int:
    """
    Принимает целое число и умножает его на два
    """
    return x * 2

@mcp.tool()
def division(a: int, b: int) -> float | str:
    """
    Принимает два целых числа и возвращает частное от деления первого на второе
    """
    if b == 0:
        return "Деление на 0 невозможно"
    return a / b


def get_local_tools():
    return [
        {
            "type": "function",
            "function": {
                "name": "multiply_by_two",
                "description": "Принимает одно целое число и возвращает его, умноженное на два",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "x": {"type": "integer"}
                    },
                    "required": ["x"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "division",
                "description": "Принимает два целых числа и возвращает частное от деления",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "a": {"type": "integer"},
                        "b": {"type": "integer"}
                    },
                    "required": ["a", "b"]
                }
            }
        }
    ]


async def fetch_remote_tools(url: str, token: str):
    tools = []
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with sse_client(url=url, headers=headers) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                response = await session.list_tools()
                for t in response.tools:
                    tools.append({
                        "type": "function",
                        "function": {
                            "name": t.name,
                            "description": t.description,
                            "parameters": t.inputSchema
                        }
                    })
    except Exception as e:
        print(f"Не удалось получить инструменты от {url}: {e}")
    return tools


async def prepare_all_tools(mcps_data):
    all_tools = []
    for cfg in mcps_data:
        if cfg["url"] == "local":
            all_tools.extend(get_local_tools())
        else:
            remote_tools = await fetch_remote_tools(cfg["url"], cfg["token"])
            all_tools.extend(remote_tools)
    return all_tools


async def call_external_mcp(mcps_data, func_name: str, arguments: dict):
    for mcp_cfg in mcps_data:
        url = mcp_cfg["url"]

        if url == "local":
            continue

        token = mcp_cfg["token"]
        headers = {"Authorization": f"Bearer {token}"}

        try:
            async with sse_client(url=url, headers=headers) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    result = await session.call_tool(func_name, arguments)
                    return result.content[0].text

        except Exception as e:
            continue

    return f"Ошибка: Инструмент '{func_name}' не найден на подключенных внешних серверах."
