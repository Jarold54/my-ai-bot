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

def deep_research(query):
    results = {}
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        url = "https://api.duckduckgo.com/?q=" + query + "&format=json&no_html=1"
        r = requests.get(url, headers=headers, timeout=5)
        data = r.json()
        abstract = data.get("AbstractText", "")
        abstract_source = data.get("AbstractSource", "")
        related = data.get("RelatedTopics", [])
        related_texts = []
        for topic in related[:5]:
            if isinstance(topic, dict) and "Text" in topic:
                related_texts.append(topic["Text"])
        if abstract:
            results["main"] = abstract
            results["source"] = abstract_source
        if related_texts:
            results["related"] = related_texts
    except:
        pass
    try:
        wiki_url = "https://en.wikipedia.org/api/rest_v1/page/summary/" + query.replace(" ", "_")
        r = requests.get(wiki_url, timeout=5)
        if r.status_code == 200:
            wiki_data = r.json()
            results["wikipedia"] = wiki_data.get("extract", "")[:500]
    except:
        pass
    try:
        news_url = "https://api.duckduckgo.com/?q=" + query + "+news&format=json&no_html=1"
        r = requests.get(news_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
        news_data = r.json()
        news_text = news_data.get("AbstractText", "")
        if news_text:
            results["news"] = news_text
    except:
        pass
    return results

def needs_search(message):
    keywords = ["latest", "today", "current", "news", "2026", "price", "now", "recent"]
    return any(word in message.lower() for word in keywords)

def needs_deep_research(message):
    keywords = ["research", "deep search", "find out", "investigate", "look into",
                "tell me everything", "what do you know about", "analyze", "study",
                "deep research", "full report", "detailed info", "explain in detail"]
    return any(word in message.lower() for word in keywords)

def needs_graph(message):
    keywords = ["chart", "graph", "plot", "visualize", "bar", "pie", "line graph",
                "show data", "diagram", "visual", "draw", "display data", "survey",
                "histogram", "scatter", "compare data", "breakdown", "distribution"]
    return any(word in message.lower() for word in keywords)

def extract_data(text):
    stop_words = {"pie", "bar", "line", "chart", "graph", "give", "me", "a", "an",
                  "with", "and", "the", "make", "into", "those", "please",
                  "create", "show", "of", "for", "to", "is", "are", "was", "pct", "percent"}
    results = []
    clean = text.lower().strip()
    clean = clean.replace("%", " percent ")
    words = clean.split()
    i = 0
    while i < len(words):
        word = words[i]
        is_number = False
        try:
            num = float(word)
            is_number = True
        except:
            pass
        if is_number:
            if i + 1 < len(words) and words[i+1] == "percent":
                if i + 2 < len(words) and words[i+2] not in stop_words:
                    results.append((words[i+2].title(), num))
                    i += 3
                    continue
            elif i + 1 < len(words) and words[i+1] not in stop_words and words[i+1] != "percent":
                results.append((words[i+1].title(), num))
                i += 2
                continue
        i += 1
    return results

def create_graph(message):
    try:
        data = extract_data(message)
        print("Extracted: " + str(data))
        if not data:
            return None
        labels = [d[0] for d in data]
        values = [d[1] for d in data]
        chart_type = "pie"
        msg = message.lower()
        if "bar" in msg:
            chart_type = "bar"
        elif "line" in msg:
            chart_type = "line"
        return json.dumps({"labels": labels, "values": values, "type": chart_type})
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
    system_prompt = "You are a helpful AI assistant that can answer questions, write and debug code, analyze data, create graphs, do deep research, and help with any task. You have long term memory. When asked for a chart or graph do not create text charts, just describe the data briefly. Always be clear and helpful." + memory_text
    search_result = ""
    research_result = ""
    research_sources = []
    if needs_deep_research(user_message):
        research_data = deep_research(user_message)
        if research_data.get("main"):
            research_result += "Main: " + research_data["main"] + " "
            if research_data.get("source"):
                research_sources.append(research_data["source"])
        if research_data.get("wikipedia"):
            research_result += "Wikipedia: " + research_data["wikipedia"] + " "
            research_sources.append("Wikipedia")
        if research_data.get("news"):
            research_result += "News: " + research_data["news"] + " "
            research_sources.append("DuckDuckGo News")
        if research_data.get("related"):
            research_result += "Related: " + " | ".join(research_data["related"][:3])
        user_message_with_context = user_message + "\n\n[Deep Research Results: " + research_result + "]"
    elif needs_search(user_message):
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
    return jsonify({"reply": reply, "searched": bool(search_result), "researched": bool(research_result), "sources": research_sources, "graph": graph_json})

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

