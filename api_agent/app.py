from fastapi import FastAPI, Header, HTTPException, Depends
from fastapi.responses import PlainTextResponse
from structures import LLM, MCP, Message, Author, LLMConfig, ChatRequest, UserRequest, OpenAIMessage
from contextlib import asynccontextmanager
import database as db
from loop import agent_loop
import openai


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.init_db()
    await db.add_user_if_not_exist("ronaldo")
    yield

app = FastAPI(lifespan=lifespan)

with open("secret.env", encoding='utf-8') as file:
    secret = file.read()

# ---------------------------AUTHENTIFICATION---------------------------
async def auth(x_username: str = Header(...), x_auth_token: str = Header(...)):
    if secret == x_auth_token:
        await db.add_user_if_not_exist(x_username)
        return x_username
    raise HTTPException(status_code=401, detail="Invalid credentials")


# ---------------------------LLM CONFIG ADDING--------------------------
@app.post("/llm-configs/add", tags=["LLM Configs"])
async def add_llm_config(llm: LLM, username: str = Depends(auth)):
    await db.add_llm_local(llm, username)
    return PlainTextResponse("OK")


# ---------------------------GET LLM CONFIGS--------------------------
@app.get("/llm-configs/all", tags=["LLM Configs"])
async def get_llm_configs(username: str = Depends(auth)):
    return await db.get_llm_local(username)


# -----------------------------MCP CONFIG ADDING-----------------------
@app.post("/mcp-configs/add", tags=["MCP Configs"])
async def add_mcp_config(mcp: MCP, username: str = Depends(auth)):
    await db.add_mcp_local(mcp, username)
    return PlainTextResponse("OK")


# -----------------------------MCP CONFIGS READING---------------------
@app.get("/mcp-configs/all", tags=["MCP Configs"])
async def get_mcp_configs(username: str = Depends(auth)):
    return await db.get_mcp_local(username)


# ---------------------------MCP ACTIVATION-----------------------------
@app.post("/chats/{chat_id}/mcp-configs/activation/{mcp_config_id}", tags=["Chats"])
async def activate_mcp_in_chat(chat_id: int, mcp_config_id: int, username: str = Depends(auth)):
    try:
        await db.activate_mcp_local(chat_id, mcp_config_id, username)
        return PlainTextResponse("OK")
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---------------------------MCP DEACTIVATION-------------------------
@app.delete("/chats/{chat_id}/mcp-configs/deactivation/{mcp_config_id}", tags=["Chats"])
async def deactivate_mcp_in_chat(chat_id: int, mcp_config_id: int, username: str = Depends(auth)):
    try:
        await db.deactivate_mcp_local(chat_id, mcp_config_id, username)
        return PlainTextResponse("OK")
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---------------------------CREATE CHAT-------------------------------
@app.post("/chats/create", tags=["Chats"])
async def create_new_chat(llm_config_id: LLMConfig, username: str = Depends(auth)):
    try:
        await db.add_chat_local(llm_config_id.id, username)
        return PlainTextResponse("OK")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---------------------------READ ALL CHATS----------------------------
@app.get("/chats/all", tags=["Chats"])
async def get_all_chats(username: str = Depends(auth)):
    return await db.get_all_chats_local(username)


# # ---------------------------ADD MESSAGE TO THE CHAT-------------------
# @app.post("/chats/{chat_id}/messages")
# async def add_message(chat_id: int, message: Message, username: str = Depends(auth)):
#     try:
#         await db.add_message_local(chat_id, Author(name=username, type="user"), message)
#         return PlainTextResponse("OK")
#     except PermissionError as e:
#         raise HTTPException(status_code=403, detail=str(e))


# ---------------------------READ CHAT HISTORY------------------------
@app.get("/chats/{chat_id}/history", tags=["Chats"])
async def read_chat_history(chat_id: int, username: str = Depends(auth)):
    try:
        return await db.read_chat_history_local(chat_id, username)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


# ---------------------------CHAT COMPLETIONS-------------------------
@app.post("/chats/{chat_id}/send_message", tags=["Chats"])
async def send_a_message_in_chosen_chat(chat_id: int, user_request: UserRequest, username: str = Depends(auth)):
    try:
        request = ChatRequest(model="",
                              messages=[OpenAIMessage(role="user", content=user_request.content)],
                              stream=user_request.stream,
                              chat_id=chat_id)

        if not request.chat_id:
            raise HTTPException(status_code=400, detail="chat_id is required")

        await db.check_user_chat(username, request.chat_id)

        user_msg = request.messages[-1].content
        await db.add_message_local(request.chat_id, Author(name=username), Message(text=user_msg), False)

        history = await db.read_chat_history_local(request.chat_id, username)
        mcps = await db.get_all_mcp_by_chat_id(request.chat_id)

        return await agent_loop(request, mcps, history)

    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except openai.APIError as e:
        status = getattr(e, 'status_code', None) or 500
        msg = getattr(e, 'message', str(e))
        raise HTTPException(status_code=status, detail=f"Ошибка LLM: {msg}")
