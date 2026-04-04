from flask import Flask, render_template, request, jsonify
import requests
import json
import os
import sqlite3
import datetime
import re
import pandas as pd
import plotly.express as px
import plotly.utils
from groq import Groq

app = Flask(__name__)
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
MODEL = "llama-3.3-70b-versatile"

def init_db():
    conn = sqlite3.connect('memory.db')
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS memories (id INTEGER PRIMARY KEY AUTOINCREMENT, type TEXT, content TEXT, timestamp TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS conversations (id INTEGER PRIMARY KEY AUTOINCREMENT, role TEXT, content TEXT, timestamp TEXT)")
    conn.commit()
    conn.close()

init_db()

def save_memory(mtype, content):
    conn = sqlite3.connect('memory.db')
    c = conn.cursor()
    c.execute("INSERT INTO memories (type, content, timestamp) VALUES (?, ?, ?)", (mtype, content, str(datetime.datetime.now())))
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
    c.execute("INSERT INTO conversations (role, content, timestamp) VALUES (?, ?, ?)", (role, content, str(datetime.datetime.now())))
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
        url = "https://api.duckduckgo.com/?q=" + query + "&format=json&no_html=1"
        response = requests.get(url, headers=headers, timeout=5)
        data = response.json()
        result = data.get("AbstractText", "")
        if not result:
            result = "Search performed for: " + query + ". No instant answer found."
        return result
    except:
        return "Web search unavailable right now."

def needs_search(message):
    keywords = ["latest", "today", "current", "news", "2026", "price", "now", "recent"]
    return any(word in message.lower() for word in keywords)

def needs_graph(message):
    keywords = ["chart", "graph", "plot", "visualize", "bar", "pie", "line graph",
                "show data", "diagram", "visual", "draw", "display data", "survey",
                "histogram", "scatter", "compare data", "breakdown", "distribution"]
    return any(word in message.lower() for word in keywords)

def extract_data(text):
    stop_words = {"pie", "bar", "line", "chart", "graph", "give", "me", "a", "an",
                  "with", "and", "the", "make", "into", "those", "please", "percent",
                  "create", "show", "of", "for", "to", "is", "are", "was", "pct"}
    clean = re.sub(r'["\'\`]', '', text.lower().strip())
    results = []
    p1 = re.findall(r'(\d+(?:\.\d+)?)\s*[%]\s*([a-z]+)', clean)
    if p1:
        for val, label in p1:
            if label not in stop_words:
                results.append((label.title(), float(val)))
        if results:
            return results
    p2 = re.findall(r'(\d+(?:\.\d+)?)\s+percent\s+([a-z]+)', clean)
    if p2:
        for val, label in p2:
            if label not in stop_words:
                results.append((label.title(), float(val)))
        if results:
            return results
    p3 = re.findall(r'([a-z]+)\s+(\d+(?:\.\d+)?)\s*[%]', clean)
    if p3:
        for label, val in p3:
            if label not in stop_words:
                results.append((label.title(), float(val)))
        if results:
            return results
    p4 = re.findall(r'([a-z]+)\s+(\d+(?:\.\d+)?)\s+percent', clean)
    if p4:
        for label, val in p4:
            if label not in stop_words:
                results.append((label.title(), float(val)))
        if results:
            return results
    return results

def create_graph(message):
    try:
        data = extract_data(message)
        print("Graph data extracted: " + str(data))
        if not data:
            return None
        labels = [d[0] for d in data]
        values = [d[1] for d in data]
        msg = message.lower()
        chart_type = "pie"
        if "bar" in msg:
            chart_type = "bar"
        elif "line" in msg:
            chart_type = "line"
        df = pd.DataFrame({"labels": labels, "values": values})
        if chart_type == "pie":
            fig = px.pie(df, names="labels", values="values", title="Chart")
        elif chart_type == "line":
            fig = px.line(df, x="labels", y="values", title="Chart")
        else:
            fig = px.bar(df, x="labels", y="values", title="Chart")
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="white")
        return json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
    except Exception as e:
        print("Graph error: " + str(e))
        return None

@app.route("/")
def home():
    return render_template("chatbot.html")

@app.route("/chat", methods=["POST"])
def chat():
    user_message = request.json.get("message")
    memories = get_memories()
    memory_text = ""
    if memories:
        memory_text = "\n\nLong term memory:\n"
        for mem_type, mem_content in memories:
            memory_text += "- [" + mem_type + "]: " + mem_content + "\n"
    recent_convos = get_recent_conversations()
    history = [{"role": role, "content": content} for role, content in recent_convos]
    system_prompt = "You are a helpful AI assistant that can answer questions, write and debug code, analyze data, create graphs, and help with any task. You have long term memory. When asked for a chart or graph do not create text charts, just describe the data briefly. Always be clear and helpful." + memory_text
    search_result = ""
    if needs_search(user_message):
        search_result = web_search(user_message)
        user_message_with_context = user_message + "\n\n[Web search result: " + search_result + "]"
    else:
        user_message_with_context = user_message
    save_conversation("user", user_message)
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "system", "content": system_prompt}] + history + [{"role": "user", "content": user_message_with_context}],
        max_tokens=1024
    )
    reply = response.choices[0].message.content
    save_conversation("assistant", reply)
    if any(word in user_message.lower() for word in ["my name is", "i am", "i like", "i prefer", "i work", "i live"]):
        save_memory("user_info", user_message)
    graph_json = None
    if needs_graph(user_message):
        full_context = user_message
        if not any(char.isdigit() for char in user_message):
            recent = get_recent_conversations()
            for role, content in reversed(recent):
                if any(char.isdigit() for char in content):
                    full_context = content + " " + user_message
                    break
        graph_json = create_graph(full_context)
    return jsonify({"reply": reply, "searched": bool(search_result), "graph": graph_json})

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

