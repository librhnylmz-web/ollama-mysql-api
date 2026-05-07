import json
import re
from pathlib import Path

import requests
from flask import Flask, request, jsonify, render_template, Response


BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"
PROMPTS_DIR = BASE_DIR / "prompts"
CONTEXT_DIR = BASE_DIR / "context"

SQL_GENERATION_PROMPT = PROMPTS_DIR / "sql_generation.md"
ANSWER_SUMMARY_PROMPT = PROMPTS_DIR / "answer_summary.md"
INTENT_DETECTION_PROMPT = PROMPTS_DIR / "intent_detection.md"
FOLLOWUP_ANSWER_PROMPT = PROMPTS_DIR / "followup_answer.md"

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

def clean_json_response(text):
    text = text.strip()

    text = re.sub(r"^```json\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    start = text.find("{")
    end = text.rfind("}")

    if start != -1 and end != -1 and end > start:
        text = text[start:end + 1]

    return text.strip()


def detect_intent(question):
    history_text = format_history_for_prompt()

    prompt = render_template_file(
        INTENT_DETECTION_PROMPT,
        {
            "history_text": history_text,
            "question": question,
        },
    )

    try:
        raw_response = ollama(prompt)
        cleaned_response = clean_json_response(raw_response)
        data = json.loads(cleaned_response)

        return {
            "needs_sql": bool(data.get("needs_sql", True)),
            "reason": data.get("reason", ""),
        }

    except Exception as e:
        print("\nIntent detection failed:")
        print(str(e))

        return {
            "needs_sql": True,
            "reason": "fallback to SQL because intent detection failed",
        }


def answer_followup(question):
    history_text = format_history_for_prompt()

    prompt = render_template_file(
        FOLLOWUP_ANSWER_PROMPT,
        {
            "history_text": history_text,
            "question": question,
        },
    )

    answer = ollama(prompt).strip()

    print("\nFollow-up answer:")
    print(answer)

    add_to_history(question, "NO_SQL", answer)

    return answer

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
    return render_template(
        "index.html",
        model=MODEL,
        database=DEFAULT_DATABASE,
    )

@app.route("/preview_sql", methods=["POST"])
def preview_sql():
    data = request.get_json(force=True)
    question = data.get("question", "").strip()

    if not question:
        return jsonify(
            {
                "success": False,
                "needs_sql": False,
                "error": "Question is empty.",
            }
        ), 400

    try:
        intent = detect_intent(question)

        if not intent["needs_sql"]:
            answer = answer_followup(question)

            return jsonify(
                {
                    "success": True,
                    "needs_sql": False,
                    "answer": answer,
                    "reason": intent.get("reason", ""),
                }
            )

        sql = generate_sql(question, DEFAULT_DATABASE)
        safe = is_safe_sql(sql)

        return jsonify(
            {
                "success": safe,
                "needs_sql": True,
                "sql": sql,
                "safe": safe,
                "reason": intent.get("reason", ""),
                "error": None if safe else "Blocked unsafe SQL by local guard.",
            }
        )

    except Exception as e:
        return jsonify(
            {
                "success": False,
                "needs_sql": False,
                "error": str(e),
            }
        ), 500

@app.route("/ask_stream", methods=["POST"])
@app.route("/ask_stream", methods=["POST"])
def ask_stream():
    data = request.get_json(force=True)
    question = data.get("question", "").strip()
    approved_sql = data.get("sql", "").strip()

    def generate():
        if not question:
            yield stream_event("error", {"error": "Question is empty."})
            return

        sql = approved_sql or None
        answer_parts = []

        try:
            if not sql:
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

            yield stream_event("status", {"message": "Running approved query through mysql-mcp-server..."})

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