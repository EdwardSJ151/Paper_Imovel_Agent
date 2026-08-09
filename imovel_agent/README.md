# imovel_agent

Conversational guide for the Unity property explorer. Served by ADK's own server.

```bash
pip install -r requirements.txt
cp .env.example .env   # add your GOOGLE_API_KEY
adk api_server         # or: adk web
```

## Unity contract

1. **Create the session once per visit**, passing the environment ID. The body is the state object
   itself — *not* wrapped in `{"state": ...}`, despite what the ADK docs show; wrapping it nests the
   value and the agent falls back to env `2`:

   ```
   POST /apps/imovel_agent/users/{userId}/sessions/{sessionId}
   {"env_id": "2"}
   ```

2. **Send each message:**

   ```
   POST /run
   {"appName":"imovel_agent","userId":"u1","sessionId":"s1",
    "newMessage":{"role":"user","parts":[{"text":"Pode me mostrar a cozinha?"}]}}
   ```

3. **Read the reply** from the last event's `content.parts[].text`. If the visitor should be moved,
   the text starts with a command block:

   ```
   <COMMAND>{"walk_to": "zone_los2rof08bacpjey"}</COMMAND>Vamos por aqui — a cozinha é integrada...
   ```

   Strip everything through `</COMMAND>`, parse the JSON, walk to that ID, and display the rest.
   No tag means stay put. `walk_to` is a `zone_*` ID for a room or an `item_*` ID for one object;
   both come straight from the scene JSON and are validated before being emitted.

## Configuration

- `scene.py` → `LANGUAGE`: `"pt"` or `"en"`. Controls the reply language. Object labels always come
  from the dictionary, which is pt-BR.
- `data/{env_id}.json` + `data/{env_id}.txt`: one scene export and one dictionary per environment,
  paired by filename (`1`, `2`, `3`). The `env_id` in session state picks the pair.
- Dictionary lines are `key = label`. The key is a mesh name, or an `item_...` ID to label one
  specific object differently from others sharing its mesh. Unlisted objects fall back to the raw
  mesh name and log a warning at load.
- Objects the export leaves outside every room polygon (wall-mounted props sit centimetres past the
  wall face) are snapped to the nearest zone by bounding-box distance.

Run `python test.py` to check all three environments end-to-end.
