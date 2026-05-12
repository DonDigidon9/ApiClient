from fastmcp import FastMCP

mcp = FastMCP("Weather-External-Server")

@mcp.tool()
def get_weather(city: str) -> str:
    """Возвращает текущую погоду в указанном городе"""
    return f"В городе {city} сейчас ясно, +24 градуса тепла."

mcp.run(transport="sse", host="127.0.0.1", port=8001)
