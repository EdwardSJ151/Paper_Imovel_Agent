"""Conversational guide for the Unity property explorer."""

from __future__ import annotations

import json
from typing import Optional

from google.adk.agents import LlmAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.models import LlmResponse
from google.adk.tools import ToolContext

from . import scene as scene_mod

DEFAULT_ENV_ID = "2"

COMMAND_OPEN = "<COMMAND>"
COMMAND_CLOSE = "</COMMAND>"

_PERSONA = {
    "pt": (
        "Voce e um corretor virtual que acompanha o visitante dentro de um imovel 3D. "
        "Responda SEMPRE em portugues do Brasil, de forma curta, calorosa e natural, "
        "como quem esta caminhando ao lado da pessoa. Traduza os nomes dos comodos "
        "para o portugues (ex.: 'Walk-in Closet' -> 'closet')."
    ),
    "en": (
        "You are a virtual real-estate agent walking a visitor through a 3D property. "
        "ALWAYS reply in English, briefly and warmly, as if strolling beside them."
    ),
}

_RULES = """
Below is the complete catalog of this property: one block per room, and inside it every object,
its category in brackets, how many there are (xN) and the ID of each copy.

Rules:
- Answer ONLY from the catalog. If something is not listed, say the property does not have it.
  Never invent objects, rooms or quantities.
- The xN counts are exact. To count a general term (e.g. "chairs"), add up every line whose
  category or name fits.
- When you locate something, mention which room it is in.
- Call the `walk_to` tool ONLY when the visitor wants to be taken/shown somewhere
  ("show me the kitchen", "where is the bed?", "take me outside"). Do not call it for pure
  counting or description questions.
  * For a room, pass the zone ID (zone_...).
  * For a specific object, pass that object's item ID (item_...). If there are several copies,
    pick one.
- Never write IDs, tags or JSON in your reply text. The navigation command is added
  automatically. Just speak naturally about what the visitor will see.
- Don't use markdown, just plain text.
""".strip()


def build_instruction(context: ReadonlyContext) -> str:
    env_id = str(context.state.get("env_id", DEFAULT_ENV_ID))
    scene = scene_mod.load_scene(env_id)
    return (
        f"{_PERSONA[scene_mod.LANGUAGE]}\n\n{_RULES}\n\n"
        f"=== PROPERTY {env_id} ===\n{scene.catalog_text}"
    )


def walk_to(target_id: str, tool_context: ToolContext) -> dict:
    """Walks the visitor to a room or to a specific object in the property.

    Use this whenever the visitor asks to be shown, taken to, or told where something is.

    Args:
        target_id (str): The ID of the destination, exactly as it appears in the catalog:
            a room ID (starting with "zone_") or a single object's ID (starting with "item_").

    Returns:
        dict: status "success" plus the label of the destination, or status "error" if the ID
            does not exist in this property.
    """
    scene = scene_mod.load_scene(str(tool_context.state.get("env_id", DEFAULT_ENV_ID)))
    if target_id not in scene.valid_ids:
        return {"status": "error", "message": f"Unknown id {target_id!r} in this property."}
    tool_context.state["walk_to"] = target_id
    return {"status": "success", "destination": scene.label_for(target_id)}


def clear_walk_to(callback_context: CallbackContext) -> None:
    """Drop last turn's destination so it can't be re-tagged onto this turn's reply."""
    callback_context.state["walk_to"] = None
    return None


def prepend_command(
    callback_context: CallbackContext, llm_response: LlmResponse
) -> Optional[LlmResponse]:
    """Prefix the spoken reply with <COMMAND>{"walk_to": ...}</COMMAND> when navigating."""
    target = callback_context.state.get("walk_to")
    if not target or not llm_response.content or not llm_response.content.parts:
        return None
    part = llm_response.content.parts[0]
    if not part.text:  # the turn that emits the functionCall carries no text
        return None
    if part.text.startswith(COMMAND_OPEN):  # this callback can fire twice on one response
        return None
    part.text = f'{COMMAND_OPEN}{json.dumps({"walk_to": target})}{COMMAND_CLOSE}' + part.text
    return llm_response


root_agent = LlmAgent(
    model="gemini-flash-latest",
    name="imovel_guide",
    description="Conversational guide for a 3D property tour.",
    instruction=build_instruction,
    tools=[walk_to],
    before_agent_callback=clear_walk_to,
    after_model_callback=prepend_command,
)
