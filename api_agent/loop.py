import json
from fastapi import HTTPException
from openai import AsyncOpenAI
import database as db
from mcp_requirements import multiply_by_two, division, prepare_all_tools, call_external_mcp
from structures import Author, Message, ChatRequest
from fastapi.responses import StreamingResponse

async def agent_loop(request: ChatRequest, mcps_data, history):
    llm_config = await db.get_llm_config_by_chat_id(request.chat_id)

    client = AsyncOpenAI(
        base_url=llm_config["base_url"],
        api_key=llm_config["api_key"],
        default_headers={"Authorization": f"Api-Key {llm_config['api_key']}"}
    )

    tools = await prepare_all_tools(mcps_data)
    messages = [{"role": "system", "content": "Ты ИИ-агент. Обязательно используй инструменты для вычислений."}]

    for msg in history:
        role = "user" if msg["author"] != "agent" else "assistant"
        messages.append({"role": role, "content": msg["content"]})

    messages.append({"role": "user", "content": request.messages[-1].content})

    iteration_count = 0
    consecutive_tool_name = None
    consecutive_tool_count = 0

    while iteration_count < 10:
        iteration_count += 1
        # print(f"--- Итерация {iteration_count} ---")

        response = await client.chat.completions.create(
            model=llm_config["model"],
            messages=messages,
            tools=tools if tools else None,
            temperature=1
        )

        llm_message = response.choices[0].message
        messages.append(llm_message.model_dump(exclude_unset=True))

        if llm_message.tool_calls:
            for tool_call in llm_message.tool_calls:
                func_name = tool_call.function.name
                arguments = json.loads(tool_call.function.arguments)
                print(f"Агент вызывает инструмент: {func_name} с аргументами {arguments}")
                if func_name == consecutive_tool_name:
                    consecutive_tool_count += 1
                    if consecutive_tool_count >= 2:
                        raise HTTPException(status_code=400, detail=f"Агент зациклился на инструменте '{func_name}'")
                else:
                    consecutive_tool_name = func_name
                    consecutive_tool_count = 1

                if func_name == "multiply_by_two":
                    result_str = str(multiply_by_two(arguments["x"]))
                elif func_name == "division":
                    result_str = str(division(arguments["a"], arguments["b"]))
                else:
                    print(f"Ищем инструмент {func_name} на внешних серверах...")
                    result_str = await call_external_mcp(mcps_data, func_name, arguments)

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": func_name,
                    "content": result_str
                })

            continue

        else:
            if request.stream:
                stream_response = await client.chat.completions.create( # type: ignore
                    model=llm_config["model"],
                    messages=messages,
                    stream=True
                )

                async def event_generator():
                    full_text = ""
                    async for chunk in stream_response: # type: ignore
                        if chunk.choices[0].delta.content:
                            content = chunk.choices[0].delta.content # type: ignore
                            full_text += content
                            yield f"data: {chunk.model_dump_json(exclude_unset=True)}\n\n"

                    yield "data: [DONE]\n\n"

                    await db.add_message_local(request.chat_id, Author(name="agent"),
                                               Message(text=full_text), True)

                return StreamingResponse(event_generator(), media_type="text/event-stream")

            else:
                final_text = llm_message.content or ""
                await db.add_message_local(request.chat_id, Author(name="agent"),
                                           Message(text=final_text), True)

                return {
                    "choices": [{
                        "message": {
                            "role": "assistant",
                            "content": final_text
                        }
                    }]
                }

    raise HTTPException(status_code=400, detail="Агентская итерация заняла более 10 completions")
