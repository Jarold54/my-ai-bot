from flask import Flask, render_template, request, jsonify
import requests
import json

app = Flask(__name__)

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "llama3:latest"

conversation_history = []
corrections = []

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
    
    system_prompt = """You are a helpful AI assistant that can answer questions, 
    write and debug code, and help with any task. You learn from corrections and 
    improve your responses. Always be clear, accurate, and helpful."""
    
    if corrections:
   system_prompt += f"\n\nIMPORTANT - Learn from these corrections: {json.dumps(corrections)}"
    
    search_result = ""
    if needs_search(user_message):
        search_result = web_search(user_message)
        user_message_with_context = f"{user_message}\n\n[Web search result: {search_result}]"
    else:
        user_message_with_context = user_message
    
    conversation_history.append({
        "role": "user",
        "content": user_message_with_context
    })
    
    payload = {
        "model": MODEL,
        "messages": [{"role": "system", "content": system_prompt}] + conversation_history,
        "stream": False
    }
    
    response = requests.post(OLLAMA_URL, json=payload)
    reply = response.json()["message"]["content"]
    
    conversation_history.append({
        "role": "assistant", 
        "content": reply
    })
    
    return jsonify({
        "reply": reply,
        "searched": bool(search_result)
    })

@app.route("/correct", methods=["POST"])
def correct():
    correction = request.json.get("correction")
    corrections.append(correction)
    return jsonify({"status": "saved", "total": len(corrections)})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
