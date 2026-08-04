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

- `scene.py` → `LANGUAGE`: `"pt"` or `"en"`. Controls the reply language and the catalog labels.
- `data/{env_id}.json`: scene export. Only `2.json` exists; drop in `1.json` / `3.json` to add the
  other properties — no code change needed.
- `data/dictionary.json`: mesh name → `{pt, en, category}`. Add an entry for every new mesh name;
  unlisted objects fall back to the raw mesh name and log a warning at load.
