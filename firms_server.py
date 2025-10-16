#!/usr/bin/env python3
# EMBER UI Flask App (header + floating chat avatars) with OpenAI backend
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import os, tempfile, datetime, re
import folium
from folium.features import DivIcon
from fires_mcp import get_active_fires_cached, get_fire_summary_by_state, get_fires_df

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
os.environ["OPENAI_API_KEY"] = "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"
app = Flask(__name__, static_folder="static")
CORS(app)

def build_map_from_db():
    df = get_fires_df()
    if df.empty:
        fmap = folium.Map(location=[39.5, -98.35], zoom_start=4, tiles="OpenStreetMap")
    else:
        fmap = folium.Map(location=[df.latitude.median(), df.longitude.median()], zoom_start=4, tiles=None)
        date = (datetime.date.today() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        folium.TileLayer(
            tiles=f"https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/"
                  f"MODIS_Terra_CorrectedReflectance_TrueColor/default/{date}/"
                  f"GoogleMapsCompatible_Level9/{{z}}/{{y}}/{{x}}.jpg",
            attr="NASA GIBS - MODIS Terra Corrected Reflectance (True Color)",
            name="NASA MODIS True Color", overlay=False, control=True, max_zoom=9
        ).add_to(fmap)
        fg = folium.FeatureGroup(name="Fires (local shapefile)", show=True)
        for _, row in df.iterrows():
            lat, lon = float(row["latitude"]), float(row["longitude"])
            conf = float(row.get("confidence", 0) or 0)
            bright = float(row.get("brightness", 0) or 0)
            color = "red" if conf >= 80 else "orange"
            size = max(10, min(26, (bright - 300) / 6))
            popup = (f"<b>{row.get('satellite','MODIS')}</b><br>{row.get('acq_date','')}<br>"
                     f"Confidence: {conf}<br>Brightness: {bright}")
            folium.Marker(location=[lat, lon], popup=popup,
                icon=DivIcon(icon_size=(size, size), icon_anchor=(size/2, size/2),
                             html=f'<div style="font-size:{int(size)}px; color:{color};">🔥</div>')).add_to(fg)
        fg.add_to(fmap)

    out_path = os.path.join(tempfile.gettempdir(), "firms_map_ember_ui.html")
    fmap.save(out_path)
    with open(out_path, "a", encoding="utf-8") as f:
        f.write("""
<style>
  :root{ --accent:#f04e23; --ink:#e8e8e8; --muted:#a9b0bd; }
  body{ margin:0; background:#0a0d18; }
  #ember-header{position:fixed; top:0; left:0; right:0; height:64px;
    background: linear-gradient(90deg,#0e1328 0%, #121a3a 60%, #0e1328 100%);
    color:var(--ink); display:flex; align-items:center; z-index:10000;
    border-bottom:1px solid rgba(255,255,255,.06);}
  #ember-header .wrap{display:flex; align-items:center; justify-content:space-between; width:100%; padding:0 16px;}
  #brand{display:flex; align-items:center; gap:12px;}
  #brand img{height:44px; width:auto; border-radius:6px;}
  #title{font:600 18px/1.1 system-ui, sans-serif; letter-spacing:.3px;}
  #right-cluster{position:relative; display:flex; align-items:center; gap:12px;}
  #ng-logo{height: 26px;
  opacity: 0.85;
  filter: contrast(110%);
  background: rgba(200, 225, 255, 0.7); /* light blue translucency */
  padding: 4px 8px; border-radius: 6px;}
  #menu-btn{background:transparent; border:1px solid rgba(255,255,255,.18); color:var(--ink);
    padding:6px 10px; border-radius:8px; cursor:pointer; font:500 13px system-ui;}
  #dropdown{position:absolute; top:44px; right:0; min-width:200px; background:#0f142e; color:var(--ink);
    border:1px solid rgba(255,255,255,.12); border-radius:10px; box-shadow:0 8px 22px rgba(0,0,0,.45);
    display:none; overflow:hidden;}
  #dropdown a{display:block; padding:10px 12px; color:var(--ink); text-decoration:none; font:500 13px system-ui;}
  #dropdown a:hover{background:rgba(255,255,255,.06);}
  #dropdown .soon{color:var(--muted); font-style:italic;}
  #map{margin-top:64px;}
  #chatbox{position:fixed; bottom:20px; right:20px; width:360px; background:#0f142e; color:#e6ebf5;
    border:1px solid rgba(255,255,255,.1); border-radius:14px; box-shadow:0 12px 30px rgba(0,0,0,.55);
    display:flex; flex-direction:column; overflow:hidden; z-index:9999; font-family:system-ui, -apple-system, Segoe UI, Roboto, sans-serif;}
  #chatbox header{background:linear-gradient(180deg,#1a2144,#131a36); color:#fff; padding:10px 12px; font-weight:600; font-size:14px; display:flex; align-items:center; gap:8px;}
  #chatbox header img{height:18px; width:18px; border-radius:50%;}
  #chatlog{padding:10px; height:240px; overflow-y:auto; font-size:14px; display:flex; flex-direction:column; gap:8px;}
  .msg{display:flex; gap:8px; align-items:flex-start;}
  .msg .avatar{width:28px; height:28px; border-radius:50%; flex:0 0 28px; background:#0b1026; display:grid; place-items:center; border:1px solid rgba(255,255,255,.15);}
  .msg .bubble{padding:8px 10px; border-radius:12px; max-width:78%;}
  .msg.user .bubble{background:#111936; color:#dbe4ff; border:1px solid rgba(255,255,255,.08);}
  .msg.bot .bubble{background:#1d2a55; color:#eff3ff; border:1px solid rgba(255,255,255,.12);}
  .name{font-weight:600; font-size:12px; color:#9ab3ff; margin-bottom:2px;}
  #inputrow{display:flex; border-top:1px solid rgba(255,255,255,.1);}
  #chatinput{width:100%; height:64px; border:0; outline:0; background:#0c1230; color:#fff; padding:10px; resize:none; font-size:14px;}
  #sendbtn{background:#f04e23; color:#fff; border:0; padding:0 14px; cursor:pointer; font-weight:600;}
  .user-icon{ width:18px; height:18px; border-radius:50%; border:2px solid #8ec8ff; position:relative;}
  .user-icon::after{ content:''; position:absolute; left:50%; top:58%; width:12px; height:6px; border:2px solid #8ec8ff; border-top:none; border-radius:0 0 16px 16px; transform:translate(-50%,-50%); }
  html, body, #map, .folium-map { height:100%; }
</style>

<div id="ember-header">
  <div class="wrap">
    <div id="brand">
      <img src="/static/ember_logo.png" alt="EMBER logo">
      <div id="title">EMBER Fire Intelligence Dashboard</div>
    </div>
    <div id="right-cluster">
      <img id="ng-logo" src="/static/ng_logo.png" alt="Northrop Grumman">
      <button id="menu-btn">Menu ▾</button>
      <div id="dropdown"><a href="#" class="soon">Coming soon</a></div>
    </div>
  </div>
</div>

<div id="chatbox" aria-live="polite">
  <header><img src="/static/ember_logo.png" alt="EMBER"> EMBER Assistant</header>
  <div id="chatlog"></div>
  <div id="inputrow">
    <textarea id="chatinput" placeholder="Ask EMBER about fires (e.g., 'How many in California?')"></textarea>
    <button id="sendbtn" onclick="sendMsg()">Send</button>
  </div>
</div>

<script>
  const menuBtn = document.getElementById('menu-btn');
  const dd = document.getElementById('dropdown');
  menuBtn.addEventListener('click', ()=>{ dd.style.display = dd.style.display === 'block' ? 'none' : 'block'; });
  document.addEventListener('click', (e)=>{ if(!document.getElementById('right-cluster').contains(e.target)) dd.style.display='none'; });

  function addMsg(role, text){
    const log = document.getElementById('chatlog');
    const wrap = document.createElement('div');
    wrap.className = 'msg ' + (role === 'user' ? 'user' : 'bot');

    const avatar = document.createElement('div');
    avatar.className = 'avatar';
    if(role === 'user'){
      const head = document.createElement('div'); head.className = 'user-icon'; avatar.appendChild(head);
    } else {
      const img = document.createElement('img'); img.src = '/static/ember_logo.png'; img.alt = 'EMBER';
      img.style.width='18px'; img.style.height='18px'; img.style.borderRadius='50%'; avatar.appendChild(img);
    }

    const bubble = document.createElement('div'); bubble.className = 'bubble';
    const name = document.createElement('div'); name.className = 'name'; name.textContent = (role === 'user') ? 'You' : 'EMBER';
    const body = document.createElement('div'); body.textContent = text;
    bubble.appendChild(name); bubble.appendChild(body);
    wrap.appendChild(avatar); wrap.appendChild(bubble);
    log.appendChild(wrap); log.scrollTop = log.scrollHeight;
  }

  async function sendMsg(){
    const ta = document.getElementById('chatinput');
    const msg = (ta.value || '').trim();
    if(!msg) return;
    addMsg('user', msg); ta.value='';
    try{
      const res = await fetch('/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:msg})});
      const data = await res.json();
      addMsg('bot', data.response || data.error || 'No reply');
    }catch(e){ addMsg('bot','Network error'); }
  }
</script>
""")
    return out_path

@app.route("/")
def root():
    return "<h3>✅ EMBER demo running</h3><p>Visit <a href='/map'>/map</a> for the map + chat.</p>"

@app.route("/map")
def map_route():
    html_path = build_map_from_db()
    return send_file(html_path)

@app.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json(force=True)
        msg = (data.get("message") or "").strip()
        if not msg:
            return jsonify({"error": "Empty message"}), 400

        m = re.search(r"\b(in|for|of)\s+([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)\b", msg)
        if m:
            state = m.group(2)
            try:
                summary = get_fire_summary_by_state(state)
                return jsonify({"response": summary})
            except Exception:
                pass

        fire_context = get_active_fires_cached(limit=10)
        clean_prompt = f"""
You are EMBER, a helpful environmental assistant with access to current US fire data.
Context:
{fire_context}

User: {msg}
Answer concisely using the context if relevant.
"""
        try:
            from openai import OpenAI
            client = OpenAI()
            resp = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role":"system","content":"You are EMBER, a concise and accurate assistant for wildfire intelligence."},
                    {"role":"user","content": clean_prompt},
                ],
                temperature=0.2,
            )
            reply = resp.choices[0].message.content.strip()
        except Exception as e:
            reply = f"Model error: {e}"
        return jsonify({"response": reply})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5001"))
    print(f"🚀 Starting EMBER UI on http://localhost:{port}/map")
    app.run(host="0.0.0.0", port=port, debug=False)
