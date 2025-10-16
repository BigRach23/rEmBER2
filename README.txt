# EMBER UI (Header + Avatars) — Deployment
- Left header: EMBER logo; Right: translucent Northrop Grumman logo with dropdown.
- Floating chat bottom-right: EMBER avatar for bot, generic head for user.
- Requires MODIS shapefile files in app root.

Run:
pip install -r requirements.txt
set OPENAI_API_KEY=sk-...   # or export on mac/linux
python firms_server.py
# open http://127.0.0.1:5001/map
