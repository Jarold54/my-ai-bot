from flask import Flask, render_template, request, jsonify
import requests
import json
import os
import sqlite3
import datetime
from groq import Groq

app = Flask(__name__)
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
MODEL = "llama-3.3-70b-versatile"

# Setup database
def init_db():
    conn = sqlite3.connect('memory.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS memories
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  type TEXT,
                  content TEXT,
                  timestamp TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS conversations
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  role TEXT,
                  content TEXT,
                  timestamp TEXT)''')
    conn.commit()
    conn.close()

init_db()

def save_memory(type, content):
    conn = sqlite3.connect('memory.db')
    c = conn.cursor()
    c.execute("INSERT INTO memories (type, content, timestamp) VALUES (?, ?, ?)",
              (type, content, str(datetime.datetime.now())))
    conn.commit()
    conn.close()

def get_memories():
    conn = sqlite3.connect('memory.db')
    c = conn.cursor()
    c.execute("SELECT type, content FROM memories ORDER BY timestamp DESC LIMIT 20")
    memories = c.fetchall()
    conn.close()
    return memories

def save_conversation(role, content):
    conn = sqlite3.connect('memory.db')
    c = conn.cursor()
    c.execute("INSERT INTO conversations (role, content, timestamp) VALUES (?, ?, ?)",
              (role, content, str(datetime.datetime.now())))
    conn.commit()
    conn.close()

def get_recent_conversations():
    conn = sqlite3.connect('memory.db')
    c = conn.cursor()
    c.execute("SELECT role, content FROM conversations ORDER BY timestamp DESC LIMIT 10")
    conversations = c.fetchall()
    conn.close()
    return list(reversed(conversations))

def web_search(query):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        url = f"https://api.duckduckgo.com/?q={query}&format=json&no_html=1"
        response = requests.get(url, headers=headers, timeout=5)
        data = response.json()
        result = data.get("AbstractText", "")
        if not result:
            result = f"Search performed for: {query}. No instant answer found."
        return result
    except:
        return "Web search unavailable right now."

def needs_search(message):
    keywords = ["latest", "today", "current", "news", "2026", "price", "now", "recent"]
    return any(word in message.lower() for word in keywords)

@app.route("/")
def home():
    return render_template("chatbot.html")

@app.route("/chat", methods=["POST"])
def chat():
    user_message = request.json.get("message")

    # Get long term memories
    memories = get_memories()
    memory_text = ""
    if memories:
        memory_text = "\n\nLong term memory (from past sessions):\n"
        for mem_type, mem_content in memories:
            memory_text += f"- [{mem_type}]: {mem_content}\n"

    # Get recent conversation history
    recent_convos = get_recent_conversations()
    history = [{"role": role, "content": content} for role, content in recent_convos]

    system_prompt = f"""You are a helpful AI assistant that can answer questions,
write and debug code, and help with any task. You have long term memory and
remember things from past conversations. Always be clear, accurate, and helpful.
{memory_text}"""

    search_result = ""
    if needs_search(user_message):
        search_result = web_search(user_message)
        user_message_with_context = f"{user_message}\n\n[Web search result: {search_result}]"
    else:
        user_message_with_context = user_message

    # Save user message to conversation history
    save_conversation("user", user_message)

    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "system", "content": system_prompt}] + history + [{"role": "user", "content": user_message_with_context}],
        max_tokens=1024
    )

    reply = response.choices[0].message.content

    # Save assistant response
    save_conversation("assistant", reply)

    # Auto save important info to memory
    if any(word in user_message.lower() for word in ["my name is", "i am", "i like", "i prefer", "i work", "i live"]):
        save_memory("user_info", user_message)

    return jsonify({
        "reply": reply,
        "searched": bool(search_result)
    })

@app.route("/correct", methods=["POST"])
def correct():
    correction = request.json.get("correction")
    save_memory("correction", correction)
    return jsonify({"status": "saved"})

@app.route("/memories", methods=["GET"])
def view_memories():
    memories = get_memories()
    return jsonify({"memories": [{"type": t, "content": c} for t, c in memories]})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
