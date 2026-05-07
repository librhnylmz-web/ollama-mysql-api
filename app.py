import json
import re
from pathlib import Path

import requests
from flask import Flask, request, jsonify, render_template_string, Response


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
  <title>Ollama MySQL IRC Chat</title>
  <style>
    :root {
      --bg: #020617;
      --panel: #0f172a;
      --panel-2: #111827;
      --line: #253047;
      --text: #d1d5db;
      --muted: #94a3b8;
      --green: #22c55e;
      --blue: #60a5fa;
      --yellow: #facc15;
      --red: #fb7185;
      --input: #020617;
    }

    * {
      box-sizing: border-box;
    }

    body {
      margin: 0;
      font-family: Consolas, Monaco, "Courier New", monospace;
      background: #020617;
      color: var(--text);
      height: 100vh;
      overflow: hidden;
    }

    .window {
      height: 100vh;
      display: grid;
      grid-template-rows: auto 1fr auto;
      background: var(--bg);
    }

    .titlebar {
      background: #020617;
      border-bottom: 1px solid var(--line);
      padding: 12px 14px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      color: var(--muted);
      font-size: 14px;
    }

    .title-left {
      display: flex;
      align-items: center;
      gap: 10px;
    }

    .dot {
      width: 12px;
      height: 12px;
      border-radius: 50%;
      background: var(--green);
      box-shadow: 0 0 12px var(--green);
    }

    .title {
      color: white;
      font-weight: bold;
    }

    .meta {
      color: #cbd5e1;
    }

    .layout {
      display: grid;
      grid-template-columns: 272px 1fr;
      min-height: 0;
    }

    .sidebar {
      border-right: 1px solid var(--line);
      background: var(--panel);
      padding: 18px 14px;
      overflow-y: auto;
    }

    .side-title {
      color: var(--yellow);
      margin-bottom: 16px;
      font-weight: bold;
      font-size: 18px;
    }

    .channel {
      padding: 8px 0;
      color: #cbd5e1;
      font-size: 17px;
    }

    .channel.active {
      color: var(--green);
      font-weight: bold;
    }

    .info-box {
      margin-top: 24px;
      padding-top: 18px;
      border-top: 1px solid var(--line);
      color: #cbd5e1;
      font-size: 13px;
      line-height: 1.6;
    }

    .info-box b {
      color: #a5b4fc;
    }

        .schema-list {
      margin-top: 8px;
    }

    .schema-table {
      color: var(--green);
      cursor: pointer;
      padding: 2px 0;
    }

    .schema-table:hover {
      color: var(--blue);
    }

    .schema-columns {
      color: var(--muted);
      font-size: 12px;
      padding-left: 12px;
      margin-bottom: 8px;
      display: none;
    }

    .schema-columns.open {
      display: block;
    }

    .chat {
      background: #020617;
      padding: 18px;
      overflow-y: auto;
      min-height: 0;
      font-size: 16px;
      line-height: 1.55;
    }

    .line {
      display: flex;
      gap: 10px;
      padding: 3px 0;
      white-space: pre-wrap;
      word-break: break-word;
    }

    .time {
      color: #64748b;
      flex: 0 0 auto;
    }

    .nick {
      flex: 0 0 auto;
      font-weight: bold;
    }

    .nick.user {
      color: var(--blue);
    }

    .nick.bot {
      color: var(--green);
    }

    .nick.system {
      color: var(--yellow);
    }

    .nick.error {
      color: var(--red);
    }

    .message {
      color: var(--text);
    }

    .sql {
      color: #a5b4fc;
      font-size: 13px;
      margin-left: 138px;
      padding: 5px 0 10px;
      white-space: pre-wrap;
      word-break: break-word;
    }

    .inputbar {
      border-top: 1px solid var(--line);
      background: #020617;
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 14px;
    }

    .prompt {
      color: var(--green);
      font-weight: bold;
      font-size: 16px;
      flex: 0 0 auto;
    }

    input {
      flex: 1;
      background: var(--input);
      border: 1px solid #3b82f6;
      color: var(--text);
      padding: 13px 14px;
      font-family: inherit;
      font-size: 16px;
      outline: none;
    }

    input:focus {
      border-color: var(--blue);
      box-shadow: 0 0 0 1px var(--blue);
    }

    button {
      background: #1f2937;
      color: var(--text);
      border: 1px solid var(--line);
      padding: 13px 18px;
      font-family: inherit;
      font-size: 15px;
      cursor: pointer;
    }

    button:hover {
      background: #334155;
    }

    button:disabled {
      opacity: 0.55;
      cursor: not-allowed;
    }
  </style>
</head>
<body>
  <div class="window">
    <div class="titlebar">
      <div class="title-left">
        <span class="dot"></span>
        <span class="title">#mysql-ollama</span>
        <span class="meta">local IRC-style database assistant</span>
      </div>
      <div class="meta">model={{ model }} | db={{ database }}</div>
    </div>

    <div class="layout">
      <aside class="sidebar">
        <div class="side-title">Channels</div>
        <div class="channel active">#mysql-ollama</div>
        <div class="channel">#demo_ai</div>
        <div class="channel">#mcp-server</div>

        <div class="info-box">
          <div><b>Flow</b></div>
          <div>User → Flask → Ollama → MCP → MySQL</div>
          <br>
          <div><b>Examples</b></div>
          <div>How many customers?</div>
          <div>Who bought Wireless Mouse?</div>
          <div>Total revenue?</div>
        </div>

        <div class="info-box">
          <div><b>System status</b></div>
          <div>Flask: <span id="health-flask">checking...</span></div>
          <div>Ollama: <span id="health-ollama">checking...</span></div>
          <div>MCP API: <span id="health-mcp">checking...</span></div>
          <div>Tables: <span id="health-tables">checking...</span></div>
        </div>

        <div class="info-box">
          <div><b>Schema</b></div>
          <div id="schema-list" class="schema-list">loading...</div>
        </div>
      </aside>

      <main id="chat" class="chat"></main>
    </div>

    <div class="inputbar">
      <span class="prompt">orhan@local&gt;</span>
      <input id="message" placeholder="Ask a database question..." autofocus />
      <button id="sendBtn" onclick="sendMessage()">Send</button>
      <button onclick="clearChat()">Clear</button>
    </div>
  </div>

  <script>
    const chat = document.getElementById("chat");
    const input = document.getElementById("message");
    const sendBtn = document.getElementById("sendBtn");

    function now() {
      const d = new Date();
      return d.toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit"
      });
    }
            function escapeText(value) {
      return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;");
    }

    function toggleSchemaColumns(id) {
      const el = document.getElementById(id);

      if (!el) {
        return;
      }

      el.classList.toggle("open");
    }

    async function loadSchema() {
      const container = document.getElementById("schema-list");

      if (!container) {
        return;
      }

      try {
        const response = await fetch("/schema");
        const data = await response.json();

        if (!data.tables || data.tables.length === 0) {
          container.textContent = "no tables found";
          return;
        }

        container.innerHTML = "";

        data.tables.forEach(function(table, index) {
          const tableId = "schema-columns-" + index;

          const tableEl = document.createElement("div");
          tableEl.className = "schema-table";
          tableEl.textContent = table.name;
          tableEl.onclick = function() {
            toggleSchemaColumns(tableId);
          };

          const columnsEl = document.createElement("div");
          columnsEl.id = tableId;
          columnsEl.className = "schema-columns";

          if (!table.columns || table.columns.length === 0) {
            columnsEl.textContent = "columns unavailable";
          } else {
            columnsEl.innerHTML = table.columns
              .map(function(column) {
                const typeText = column.type ? " " + column.type : "";
                return escapeText(column.name + typeText);
              })
              .join("<br>");
          }

          container.appendChild(tableEl);
          container.appendChild(columnsEl);
        });
      } catch (err) {
        container.textContent = "schema unavailable";
      }
    }
        function setHealthText(id, text, ok) {
      const el = document.getElementById(id);

      if (!el) {
        return;
      }

      el.textContent = text;
      el.style.color = ok ? "var(--green)" : "var(--red)";
    }

    async function loadHealth() {
      try {
        const response = await fetch("/health");
        const data = await response.json();

        setHealthText("health-flask", data.flask.status, data.flask.status === "ok");
        setHealthText("health-ollama", data.ollama.status, data.ollama.status === "ok");
        setHealthText("health-mcp", data.mcp.status, data.mcp.status === "ok");

        if (data.mcp.status === "ok") {
          setHealthText("health-tables", String(data.mcp.table_count), true);
        } else {
          setHealthText("health-tables", "error", false);
        }
      } catch (err) {
        setHealthText("health-flask", "error", false);
        setHealthText("health-ollama", "unknown", false);
        setHealthText("health-mcp", "unknown", false);
        setHealthText("health-tables", "unknown", false);
      }
    }

    function addLine(nick, text, type = "bot") {
      const line = document.createElement("div");
      line.className = "line";

      const time = document.createElement("span");
      time.className = "time";
      time.textContent = "[" + now() + "]";

      const nickEl = document.createElement("span");
      nickEl.className = "nick " + type;
      nickEl.textContent = "<" + nick + ">";

      const msg = document.createElement("span");
      msg.className = "message";
      msg.textContent = text;

      line.appendChild(time);
      line.appendChild(nickEl);
      line.appendChild(msg);

      chat.appendChild(line);
      chat.scrollTop = chat.scrollHeight;

      return msg;
    }

    function addSql(sql) {
      const div = document.createElement("div");
      div.className = "sql";
      div.textContent = "SQL> " + sql;
      chat.appendChild(div);
      chat.scrollTop = chat.scrollHeight;
    }

    async function sendMessage() {
      const question = input.value.trim();
      if (!question) return;

      input.value = "";
      sendBtn.disabled = true;
      input.disabled = true;

      addLine("you", question, "user");
      const botMessage = addLine("dbbot", "working...", "bot");

      try {
        const response = await fetch("/ask_stream", {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify({ question })
        });

        if (!response.ok || !response.body) {
          botMessage.textContent = "Request failed.";
          return;
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder("utf-8");

        let buffer = "";
        let firstToken = true;

        while (true) {
          const { value, done } = await reader.read();

          if (done) {
            break;
          }

          buffer += decoder.decode(value, { stream: true });

          const lines = buffer.split("\\n");
          buffer = lines.pop();

          for (const line of lines) {
            if (!line.trim()) continue;

            let data;

            try {
              data = JSON.parse(line);
            } catch (err) {
              console.error("Stream parse error:", err, line);
              continue;
            }

            if (data.event === "status") {
              botMessage.textContent = data.message;
              chat.scrollTop = chat.scrollHeight;
            }

            if (data.event === "sql") {
              addSql(data.sql);
            }

            if (data.event === "token") {
              if (firstToken) {
                botMessage.textContent = "";
                firstToken = false;
              }

              botMessage.textContent += data.token;
              chat.scrollTop = chat.scrollHeight;
            }

            if (data.event === "error") {
              botMessage.textContent = "Error: " + data.error;

              if (data.sql) {
                addSql(data.sql);
              }

              chat.scrollTop = chat.scrollHeight;
            }

            if (data.event === "done") {
              chat.scrollTop = chat.scrollHeight;
            }
          }
        }

      } catch (err) {
        botMessage.textContent = "Error: " + err;
      } finally {
        sendBtn.disabled = false;
        input.disabled = false;
        input.focus();
      }
    }

    async function clearChat() {
      await fetch("/clear", { method: "POST" });
      chat.innerHTML = "";
      addLine("system", "Chat history cleared.", "system");
    }

    input.addEventListener("keydown", function(event) {
      if (event.key === "Enter") {
        sendMessage();
      }
    });

    addLine("system", "Connected to #mysql-ollama.", "system");
    addLine("system", "Ask a question about demo_ai database.", "system");
    loadHealth();
    setInterval(loadHealth, 30000);
    loadSchema();
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


def ollama_stream(prompt):
    print("\nStarting Ollama answer stream...", flush=True)

    response = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL,
            "prompt": prompt,
            "stream": True,
        },
        stream=True,
        timeout=120,
    )
    response.raise_for_status()

    for line in response.iter_lines():
        if not line:
            continue

        data = json.loads(line.decode("utf-8"))

        if "response" in data:
            token = data["response"]
            print(token, end="", flush=True)
            yield token

        if data.get("done"):
            print("\nOllama answer stream finished.", flush=True)
            break


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

    lines = text.splitlines()

    sql_lines = []
    sql_started = False

    for line in lines:
        stripped = line.strip()

        if not stripped:
            continue

        if not sql_started:
            if stripped.lower().startswith(("select", "show", "describe", "desc", "explain")):
                sql_started = True
                sql_lines.append(stripped)
            continue

        sql_lines.append(stripped)

    if sql_lines:
        text = " ".join(sql_lines)
    else:
        text = text.replace("\n", " ").strip()

    if ";" in text:
        text = text.split(";")[0]

    return text.strip() + ";"


def is_safe_sql(sql):
    lowered = sql.lower().strip()
    sql_without_final_semicolon = lowered[:-1] if lowered.endswith(";") else lowered

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
        "information_schema",
        "performance_schema",
        "mysql.",
        "sys.",
    ]

    blocked_patterns = [
        "--",
        "/*",
        "*/",
        "#",
    ]

    if not any(lowered.startswith(prefix) for prefix in allowed_prefixes):
        return False

    if ";" in sql_without_final_semicolon:
        return False

    if any(word in lowered for word in blocked_words):
        return False

    if any(pattern in lowered for pattern in blocked_patterns):
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


def build_summary_prompt(question, sql, result):
    history_text = format_history_for_prompt()

    return render_template_file(
        ANSWER_SUMMARY_PROMPT,
        {
            "history_text": history_text,
            "question": question,
            "sql": sql,
            "result": json.dumps(result, indent=2, ensure_ascii=False),
        },
    )


def stream_event(event_name, payload):
    data = {
        "event": event_name,
        **payload,
    }

    return json.dumps(data, ensure_ascii=False) + "\n"

def check_ollama_health():
    try:
        ollama_base_url = OLLAMA_URL.replace("/api/generate", "")
        response = requests.get(f"{ollama_base_url}/api/tags", timeout=5)
        response.raise_for_status()

        return {
            "status": "ok",
            "model": MODEL,
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
        }


def check_mcp_health():
    try:
        tables_response = get_tables(DEFAULT_DATABASE)
        table_names = extract_table_names(tables_response)

        return {
            "status": "ok",
            "database": DEFAULT_DATABASE,
            "table_count": len(table_names),
            "tables": table_names,
        }
    except Exception as e:
        return {
            "status": "error",
            "database": DEFAULT_DATABASE,
            "error": str(e),
        }


@app.route("/health")
def health():
    ollama_health = check_ollama_health()
    mcp_health = check_mcp_health()

    overall_status = "ok"

    if ollama_health["status"] != "ok" or mcp_health["status"] != "ok":
        overall_status = "error"

    return jsonify(
        {
            "status": overall_status,
            "flask": {
                "status": "ok",
            },
            "ollama": ollama_health,
            "mcp": mcp_health,
        }
    )

@app.route("/schema")
def schema():
    schema_context = build_schema_context(DEFAULT_DATABASE)

    tables = []

    for table_name, table_schema in schema_context.get("schemas", {}).items():
        columns = []

        def walk(value):
            if isinstance(value, dict):
                column_name = None
                column_type = None

                for key, item in value.items():
                    lowered_key = key.lower()

                    if lowered_key in ["field", "column", "column_name", "name"]:
                        if isinstance(item, str):
                            column_name = item

                    if lowered_key in ["type", "data_type"]:
                        if isinstance(item, str):
                            column_type = item

                if column_name:
                    columns.append(
                        {
                            "name": column_name,
                            "type": column_type or "",
                        }
                    )

                for item in value.values():
                    walk(item)

            elif isinstance(value, list):
                for item in value:
                    walk(item)

        walk(table_schema)

        unique_columns = []
        seen = set()

        for column in columns:
            if column["name"] not in seen:
                unique_columns.append(column)
                seen.add(column["name"])

        tables.append(
            {
                "name": table_name,
                "columns": unique_columns,
            }
        )

    return jsonify(
        {
            "database": DEFAULT_DATABASE,
            "tables": tables,
        }
    )

@app.route("/")
def index():
    return render_template_string(
        HTML,
        model=MODEL,
        database=DEFAULT_DATABASE,
    )


@app.route("/ask_stream", methods=["POST"])
def ask_stream():
    data = request.get_json(force=True)
    question = data.get("question", "").strip()

    def generate():
        if not question:
            yield stream_event("error", {"error": "Question is empty."})
            return

        sql = None
        answer_parts = []

        try:
            yield stream_event("status", {"message": "Generating SQL..."})

            sql = generate_sql(question, DEFAULT_DATABASE)

            yield stream_event("sql", {"sql": sql})

            if not is_safe_sql(sql):
                yield stream_event(
                    "error",
                    {
                        "error": "Blocked unsafe SQL by local guard.",
                        "sql": sql,
                    },
                )
                return

            yield stream_event("status", {"message": "Running query through mysql-mcp-server..."})

            result = run_query(sql, DEFAULT_DATABASE)

            print("\nRaw API result:")
            print(json.dumps(result, indent=2, ensure_ascii=False))

            yield stream_event("status", {"message": "Summarizing answer..."})

            summary_prompt = build_summary_prompt(question, sql, result)

            for token in ollama_stream(summary_prompt):
                answer_parts.append(token)
                yield stream_event("token", {"token": token})

            final_answer = "".join(answer_parts).strip()
            add_to_history(question, sql, final_answer)

            yield stream_event("done", {"success": True})

        except requests.exceptions.HTTPError as e:
            error_text = str(e)

            if e.response is not None:
                error_text += " " + e.response.text

            yield stream_event(
                "error",
                {
                    "error": error_text,
                    "sql": sql,
                },
            )

        except Exception as e:
            yield stream_event(
                "error",
                {
                    "error": str(e),
                    "sql": sql,
                },
            )

    return Response(
        generate(),
        mimetype="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.route("/clear", methods=["POST"])
def clear():
    conversation_history.clear()
    return jsonify({"success": True})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True, threaded=True)