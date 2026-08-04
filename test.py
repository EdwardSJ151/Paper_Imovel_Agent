"""Runs the agent in-process and checks the replies. No server needed: python test.py"""

import asyncio
import re

from dotenv import load_dotenv
from google.adk.runners import InMemoryRunner
from google.genai import types

load_dotenv()

from imovel_agent.agent import root_agent  # noqa: E402  (after load_dotenv)

APP = "imovel_agent"
ENV_ID = "2"

# (question, expected walk_to id — None means the reply must carry no <COMMAND> tag)
TURNS = [
    ("Quantas cadeiras tem na cozinha?", None),
    ("Quantas TVs tem nessa casa?", None),
    ("Pode me mostrar a cozinha?", "zone_los2rof08bacpjey"),
    ("Onde fica a cama?", "item_7yokdcbfr3e14jc3"),
    ("E quantas plantas tem no total?", None),
    ("O que tem no terraco?", None),
]

TAG = re.compile(r'<COMMAND>(.*?)</COMMAND>')


def check(reply: str, expected: str | None) -> str:
    tags = TAG.findall(reply)
    if len(tags) > 1:
        return f"FAIL: {len(tags)} command tags, expected at most 1"
    if expected is None:
        return "PASS" if not tags else f"FAIL: expected no tag, got {tags[0]}"
    if not tags:
        return f"FAIL: expected walk_to {expected}, got no tag"
    if f'"{expected}"' not in tags[0]:
        return f"FAIL: expected walk_to {expected}, got {tags[0]}"
    if not reply.split("</COMMAND>", 1)[1].strip():
        return "FAIL: tag present but no prose after it"
    return "PASS"


async def main():
    runner = InMemoryRunner(agent=root_agent, app_name=APP)
    session = await runner.session_service.create_session(
        app_name=APP, user_id="u1", state={"env_id": ENV_ID}
    )

    results = []
    for question, expected in TURNS:
        print("=" * 78)
        print(f"> {question}")
        print("-" * 78)

        reply = ""
        async for event in runner.run_async(
            user_id="u1",
            session_id=session.id,
            new_message=types.Content(role="user", parts=[types.Part(text=question)]),
        ):
            for part in (event.content.parts if event.content else []) or []:
                if part.function_call:
                    print(f"  [tool] {part.function_call.name}({part.function_call.args})")
                elif part.text and event.author != "user":
                    reply += part.text

        reply = reply.strip()
        print(reply or "(sem resposta)")
        verdict = check(reply, expected)
        results.append(verdict)
        print(f"\n  -> {verdict}\n")

    print("=" * 78)
    failed = [r for r in results if r.startswith("FAIL")]
    print(f"{len(results) - len(failed)}/{len(results)} passed")
    for r in failed:
        print(f"  {r}")
    print("\nCounting and hallucination still need your eyes: 6 cadeiras da cozinha, zero TVs, "
          "3 plantas (grama, vaso de flor, palmeira).")

    await runner.close()


if __name__ == "__main__":
    asyncio.run(main())
