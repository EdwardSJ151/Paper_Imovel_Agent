"""Checks that each environment answers from its own scene. No server needed: python test.py"""

import asyncio
import re

from dotenv import load_dotenv
from google.adk.runners import InMemoryRunner
from google.genai import types

load_dotenv()

from imovel_agent import scene  # noqa: E402  (after load_dotenv)
from imovel_agent.agent import root_agent  # noqa: E402

APP = "imovel_agent"

# (question, should it navigate?)
TURNS = [
    ("Quantas cadeiras tem na casa?", False),
    ("Quais comodos ficam ao lado da cozinha? E qual o tamanho dela?", False),
    ("Pode me mostrar a cozinha?", True),
]

TAG = re.compile(r"<COMMAND>(.*?)</COMMAND>")


def check(reply: str, navigates: bool, env_id: str) -> str:
    tags = TAG.findall(reply)
    if len(tags) > 1:
        return f"FAIL: {len(tags)} command tags, expected at most 1"
    if not navigates:
        return "PASS" if not tags else f"FAIL: expected no tag, got {tags[0]}"
    if not tags:
        return "FAIL: expected a walk_to tag, got none"
    target = re.search(r'"walk_to": "(.*?)"', tags[0]).group(1)
    if target not in scene.load_scene(env_id).valid_ids:
        return f"FAIL: {target} does not belong to environment {env_id}"
    if not reply.split("</COMMAND>", 1)[1].strip():
        return "FAIL: tag present but no prose after it"
    return f"PASS ({scene.load_scene(env_id).label_for(target)})"


async def run_env(runner: InMemoryRunner, env_id: str) -> list[str]:
    session = await runner.session_service.create_session(
        app_name=APP, user_id=f"u{env_id}", state={"env_id": env_id}
    )
    results = []
    for question, navigates in TURNS:
        reply = ""
        async for event in runner.run_async(
            user_id=f"u{env_id}",
            session_id=session.id,
            new_message=types.Content(role="user", parts=[types.Part(text=question)]),
        ):
            for part in (event.content.parts if event.content else []) or []:
                if part.text and event.author != "user":
                    reply += part.text

        reply = reply.strip()
        verdict = check(reply, navigates, env_id)
        results.append(verdict)
        print(f"> {question}")
        print(f"  {reply or '(sem resposta)'}")
        print(f"  -> {verdict}\n")
    return results


async def main():
    ids = [str(n) for n in (1, 2, 3)]

    # The IDs are per-export, so a leak between environments is impossible to miss.
    for env_id in ids:
        other = set().union(*(scene.load_scene(o).valid_ids for o in ids if o != env_id))
        assert not (scene.load_scene(env_id).valid_ids & other), f"env {env_id} shares IDs"

    runner = InMemoryRunner(agent=root_agent, app_name=APP)
    results = []
    for env_id in ids:
        s = scene.load_scene(env_id)
        print("=" * 78)
        print(f"AMBIENTE {env_id}: {len(s.valid_ids)} ids")
        print("=" * 78)
        results += await run_env(runner, env_id)

    failed = [r for r in results if r.startswith("FAIL")]
    print(f"{len(results) - len(failed)}/{len(results)} passed")
    for r in failed:
        print(f"  {r}")

    await runner.close()


if __name__ == "__main__":
    asyncio.run(main())
