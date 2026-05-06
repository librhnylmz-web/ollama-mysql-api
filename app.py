import json
import re
from pathlib import Path

import requests
from flask import Flask, request, jsonify, render_template_string


BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"
PROMPTS_DIR = BASE_DIR / "prompts"
CONTEXT_DIR = BASE_DIR / "context"

SQL_GENERATION_PROMPT = PROMPTS_DIR / "sql_generation.md"
ANSWER_SUMMARY_PROMPT = PROMPTS_DIR / "answer_summary.md"

conversation_history = []


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as file:
        return json.load(file)


CONFIG = load_config()

OLLAMA_URL = CONFIG["ollama_url"]
MCP_API_BASE = CONFIG["mcp_api_base"]
MODEL = CONFIG["model"]
DEFAULT_DATABASE = CONFIG["default_database"]
MAX_HISTORY_ITEMS = CONFIG.get("max_history_items", 5)
MAX_SCHEMA_TABLES = CONFIG.get("max_schema_tables", 10)

MCP_API_QUERY_URL = f"{MCP_API_BASE}/query"
MCP_API_TABLES_URL = f"{MCP_API_BASE}/tables"
MCP_API_DESCRIBE_URL = f"{MCP_API_BASE}/describe"


app = Flask(__name__)


HTML = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>MySQL + Ollama Chatbot</title>
  <style>
    body {
      font-family: Arial, sans-serif;
      background: #f5f7fb;
      margin: 0;
      padding: 0;
    }

    .container {
      max-width: 900px;
      margin: 40px auto;
      background: white;
      border-radius: 14px;
      box-shadow: 0 8px 30px rgba(0,0,0,0.08);
      overflow: hidden;
    }

    .header {
      background: #111827;
      color: white;
      padding: 18px 24px;
    }

    .header h1 {
      margin: 0;
      font-size: 22px;
    }

    .header p {
      margin: 6px 0 0 0;
      color: #cbd5e1;
      font-size: 14px;
    }

    .chat {
      height: 520px;
      overflow-y: auto;
      padding: 24px;
      background: #f8fafc;
    }

    .msg {
      margin-bottom: 16px;
      max-width: 78%;
      padding: 12px 14px;
      border-radius: 12px;
      line-height: 1.4;
      white-space: pre-wrap;
    }

    .user {
      background: #2563eb;
      color: white;
      margin-left: auto;
    }

    .bot {
      background: white;
      color: #111827;
      border: 1px solid #e5e7eb;
    }

    .meta {
      font-size: 12px;
      color: #6b7280;
      margin-top: 8px;
      border-top: 1px solid #e5e7eb;
      padding-top: 8px;
      white-space: pre-wrap;
    }

    .input-area {
      display: flex;
      gap: 10px;
      padding: 16px;
      border-top: 1px solid #e5e7eb;
      background: white;
    }

    input {
      flex: 1;
      padding: 12px;
      border: 1px solid #d1d5db;
      border-radius: 10px;
      font-size: 15px;
    }

    button {
      padding: 12px 18px;
      border: none;
      border-radius: 10px;
      background: #111827;
      color: white;
      cursor: pointer;
      font-size: 15px;
    }

    button:hover {
      background: #374151;
    }

    .small-button {
      background: #6b7280;
    }

    .small-button:hover {
      background: #4b5563;
    }
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>MySQL + Ollama Chatbot</h1>
      <p>Model: {{ model }} | Database: {{ database }}</p>
    </div>

    <div id="chat" class="chat"></div>

    <div class="input-area">
      <input id="message" placeholder="Ask something, e.g. Can you list our customers?" autofocus />
      <button onclick="sendMessage()">Send</button>
      <button class="small-button" onclick="clearChat()">Clear</button>
    </div>
  </div>

  <script>
    const chat = document.getElementById("chat");
    const input = document.getElementById("message");

    function addMessage(text, type, meta = null) {
      const div = document.createElement("div");
      div.className = "msg " + type;
      div.textContent = text;

      if (meta) {
        const metaDiv = document.createElement("div");
        metaDiv.className = "meta";
        metaDiv.textContent = meta;
        div.appendChild(metaDiv);
      }

      chat.appendChild(div);
      chat.scrollTop = chat.scrollHeight;
    }

    async function sendMessage() {
      const text = input.value.trim();
      if (!text) return;

      addMessage(text, "user");
      input.value = "";

      addMessage("Thinking...", "bot");

      try {
        const response = await fetch("/ask", {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify({ question: text })
        });

        const data = await response.json();

        chat.removeChild(chat.lastChild);

        if (!data.success) {
          let meta = "";
          if (data.sql) {
            meta = "Generated SQL:\\n" + data.sql;
          }
          addMessage("Error: " + data.error, "bot", meta);
          return;
        }

        let meta = "";
        if (data.sql) {
          meta = "Generated SQL:\\n" + data.sql;
        }

        addMessage(data.answer, "bot", meta);

      } catch (err) {
        chat.removeChild(chat.lastChild);
        addMessage("Request failed: " + err, "bot");
      }
    }

    async function clearChat() {
      await fetch("/clear", { method: "POST" });
      chat.innerHTML = "";
      addMessage("Chat history cleared.", "bot");
    }

    input.addEventListener("keydown", function(event) {
      if (event.key === "Enter") {
        sendMessage();
      }
    });

    addMessage("Ready. Ask me about the demo_ai database.", "bot");
  </script>
</body>
</html>
"""


def load_prompt_template(path):
    with open(path, "r", encoding="utf-8") as file:
        return file.read()


def render_template_file(path, variables):
    template = load_prompt_template(path)

    for key, value in variables.items():
        template = template.replace("{{" + key + "}}", str(value))

    return template


def load_business_context(database):
    context_path = CONTEXT_DIR / f"{database}.md"

    if not context_path.exists():
        return "No business context file found for this database."

    with open(context_path, "r", encoding="utf-8") as file:
        return file.read()


def ollama(prompt):
    response = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL,
            "prompt": prompt,
            "stream": False,
        },
        timeout=120,
    )
    response.raise_for_status()
    return response.json()["response"].strip()


def api_get(url, params=None):
    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def api_post(url, payload):
    response = requests.post(
        url,
        headers={"Content-Type": "application/json"},
        json=payload,
        timeout=60,
    )
    response.raise_for_status()
    return response.json()


def get_tables(database):
    return api_get(MCP_API_TABLES_URL, params={"database": database})


def get_table_schema(database, table):
    return api_get(
        MCP_API_DESCRIBE_URL,
        params={
            "database": database,
            "table": table,
        },
    )


def run_query(sql, database):
    return api_post(
        MCP_API_QUERY_URL,
        {
            "sql": sql,
            "database": database,
        },
    )


def clean_sql(text):
    text = text.strip()

    text = re.sub(r"^```sql\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    lines = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        if line.lower().startswith(("select", "show", "describe", "desc", "explain")):
            lines = [line]
            break

        lines.append(line)

    text = " ".join(lines)

    if ";" in text:
        text = text.split(";")[0]

    return text.strip() + ";"


def is_safe_sql(sql):
    lowered = sql.lower().strip()

    allowed_prefixes = [
        "select",
        "show",
        "describe",
        "desc",
        "explain",
    ]

    blocked_words = [
        "insert",
        "update",
        "delete",
        "drop",
        "alter",
        "truncate",
        "create",
        "replace",
        "grant",
        "revoke",
        "set ",
        "use ",
        "call",
        "load",
        "outfile",
        "dumpfile",
        "infile",
        "sleep",
        "benchmark",
        "load_file",
        "get_lock",
    ]

    if not any(lowered.startswith(prefix) for prefix in allowed_prefixes):
        return False

    if any(word in lowered for word in blocked_words):
        return False

    return True


def extract_table_names(tables_response):
    names = []

    def walk(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key.lower() in ["table", "table_name", "name"]:
                    if isinstance(item, str):
                        names.append(item)
                else:
                    walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(tables_response)

    result = []
    for name in names:
        if name not in result:
            result.append(name)

    return result


def build_schema_context(database):
    context = {}

    try:
        tables_response = get_tables(database)
        context["tables_response"] = tables_response
    except Exception as e:
        context["tables_error"] = str(e)
        return context

    table_names = extract_table_names(tables_response)

    schemas = {}
    for table in table_names[:MAX_SCHEMA_TABLES]:
        try:
            schemas[table] = get_table_schema(database, table)
        except Exception as e:
            schemas[table] = {"error": str(e)}

    context["schemas"] = schemas
    return context


def format_history_for_prompt():
    if not conversation_history:
        return "No previous conversation."

    recent_history = conversation_history[-MAX_HISTORY_ITEMS:]

    parts = []
    for index, item in enumerate(recent_history, start=1):
        parts.append(
            f"""
Conversation {index}
User question: {item.get("question")}
SQL: {item.get("sql")}
Short answer: {item.get("answer")}
"""
        )

    return "\n".join(parts)


def add_to_history(question, sql, answer):
    conversation_history.append(
        {
            "question": question,
            "sql": sql,
            "answer": answer,
        }
    )


def generate_sql(question, database):
    schema_context = build_schema_context(database)
    business_context = load_business_context(database)
    history_text = format_history_for_prompt()

    prompt = render_template_file(
        SQL_GENERATION_PROMPT,
        {
            "database": database,
            "schema_context": json.dumps(schema_context, indent=2, ensure_ascii=False),
            "business_context": business_context,
            "history_text": history_text,
            "question": question,
        },
    )

    sql = clean_sql(ollama(prompt))

    print("\nGenerated SQL:")
    print(sql)

    return sql


def summarize_answer(question, sql, result):
    history_text = format_history_for_prompt()

    prompt = render_template_file(
        ANSWER_SUMMARY_PROMPT,
        {
            "history_text": history_text,
            "question": question,
            "sql": sql,
            "result": json.dumps(result, indent=2, ensure_ascii=False),
        },
    )

    return ollama(prompt)


def answer_question(question, database):
    sql = generate_sql(question, database)

    if not is_safe_sql(sql):
        return {
            "success": False,
            "error": "Blocked unsafe SQL by local guard.",
            "sql": sql,
        }

    result = run_query(sql, database)

    print("\nRaw API result:")
    print(json.dumps(result, indent=2, ensure_ascii=False))

    answer = summarize_answer(question, sql, result)

    add_to_history(question, sql, answer)

    return {
        "success": True,
        "sql": sql,
        "raw_result": result,
        "answer": answer,
    }


@app.route("/")
def index():
    return render_template_string(
        HTML,
        model=MODEL,
        database=DEFAULT_DATABASE,
    )


@app.route("/ask", methods=["POST"])
def ask():
    try:
        data = request.get_json(force=True)
        question = data.get("question", "").strip()

        if not question:
            return jsonify(
                {
                    "success": False,
                    "error": "Question is empty.",
                }
            ), 400

        response = answer_question(question, DEFAULT_DATABASE)
        status_code = 200 if response.get("success") else 400
        return jsonify(response), status_code

    except requests.exceptions.ConnectionError as e:
        return jsonify(
            {
                "success": False,
                "error": f"Connection error. Check Ollama and mysql-mcp-server. {e}",
            }
        ), 500

    except requests.exceptions.HTTPError as e:
        error_text = str(e)

        if e.response is not None:
            error_text += " " + e.response.text

        return jsonify(
            {
                "success": False,
                "error": error_text,
            }
        ), 500

    except Exception as e:
        return jsonify(
            {
                "success": False,
                "error": str(e),
            }
        ), 500


@app.route("/clear", methods=["POST"])
def clear():
    conversation_history.clear()
    return jsonify({"success": True})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
