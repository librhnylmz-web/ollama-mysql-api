import json
import re
from pathlib import Path

import requests


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

MCP_API_DATABASES_URL = f"{MCP_API_BASE}/databases"
MCP_API_QUERY_URL = f"{MCP_API_BASE}/query"
MCP_API_TABLES_URL = f"{MCP_API_BASE}/tables"
MCP_API_DESCRIBE_URL = f"{MCP_API_BASE}/describe"


def load_prompt_template(path):
    with open(path, "r", encoding="utf-8") as file:
        return file.read()


def render_template(path, variables):
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


def get_databases():
    return api_get(MCP_API_DATABASES_URL)


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

    prompt = render_template(
        SQL_GENERATION_PROMPT,
        {
            "database": database,
            "schema_context": json.dumps(schema_context, indent=2, ensure_ascii=False),
            "business_context": business_context,
            "history_text": history_text,
            "question": question,
        },
    )

    return clean_sql(ollama(prompt))

def summarize_answer(question, sql, result):
    history_text = format_history_for_prompt()

    prompt = render_template(
        ANSWER_SUMMARY_PROMPT,
        {
            "history_text": history_text,
            "question": question,
            "sql": sql,
            "result": json.dumps(result, indent=2, ensure_ascii=False),
        },
    )

    return ollama(prompt)


def looks_like_database_list_question(question):
    q = question.lower()

    patterns = [
        "list all my databases",
        "show databases",
        "list databases",
        "database list",
        "databases",
        "tüm database",
        "databaseleri listele",
        "veritabanlarını listele",
        "veritabanlari listele",
    ]

    return any(pattern in q for pattern in patterns)


def looks_like_table_list_question(question):
    q = question.lower()

    patterns = [
        "list tables",
        "show tables",
        "tables",
        "tablolar",
        "tabloları listele",
        "tablolari listele",
    ]

    return any(pattern in q for pattern in patterns)


def handle_database_list():
    result = get_databases()

    print("\nDatabases:")
    print(json.dumps(result, indent=2, ensure_ascii=False))

    add_to_history(
        question="List databases",
        sql="SHOW DATABASES;",
        answer=json.dumps(result, ensure_ascii=False),
    )


def handle_table_list(database):
    result = get_tables(database)

    print(f"\nTables in {database}:")
    print(json.dumps(result, indent=2, ensure_ascii=False))

    add_to_history(
        question=f"List tables in {database}",
        sql=f"SHOW TABLES FROM {database};",
        answer=json.dumps(result, ensure_ascii=False),
    )


def answer_question(question, database):
    if looks_like_database_list_question(question):
        handle_database_list()
        return database

    if looks_like_table_list_question(question):
        handle_table_list(database)
        return database

    sql = generate_sql(question, database)

    print("\nGenerated SQL:")
    print(sql)

    if not is_safe_sql(sql):
        print("\nBlocked unsafe SQL by local guard.")
        return database

    result = run_query(sql, database)

    print("\nRaw API result:")
    print(json.dumps(result, indent=2, ensure_ascii=False))

    answer = summarize_answer(question, sql, result)

    print("\nAnswer:")
    print(answer)

    add_to_history(question, sql, answer)

    return database


def show_history():
    if not conversation_history:
        print("\nHistory is empty.")
        return

    print("\nConversation history:")
    for index, item in enumerate(conversation_history, start=1):
        print(f"\n[{index}]")
        print(f"Question: {item.get('question')}")
        print(f"SQL: {item.get('sql')}")
        print(f"Answer: {item.get('answer')}")


def clear_history():
    conversation_history.clear()
    print("\nHistory cleared.")


def print_help():
    print("""
Commands:
  help                    Show this help
  exit / quit / q          Exit
  db                      Show current database
  db <database_name>       Change current database
  databases               List databases
  tables                  List tables in current database
  history                 Show conversation history
  clear                   Clear conversation history

Examples:
  list all my databases
  show tables
  list all customers
  how many customers are in Berlin?
  what about Hamburg?
""")


def main():
    current_database = DEFAULT_DATABASE

    print("MySQL + Ollama shell started.")
    print(f"Model: {MODEL}")
    print(f"Current database: {current_database}")
    print("History: enabled in memory")
    print("Prompts: loaded from ./prompts/*.md")
    print("Type help for commands.")
    print("Type exit or quit to leave.\n")

    while True:
        try:
            question = input(f"{current_database}> ").strip()

            if not question:
                continue

            lowered = question.lower()

            if lowered in ["exit", "quit", "q"]:
                print("Bye.")
                break

            if lowered == "help":
                print_help()
                continue

            if lowered == "history":
                show_history()
                continue

            if lowered == "clear":
                clear_history()
                continue

            if lowered == "db":
                print(f"Current database: {current_database}")
                continue

            if lowered.startswith("db "):
                new_database = question[3:].strip()

                if not new_database:
                    print("Please provide a database name.")
                    continue

                current_database = new_database
                print(f"Current database changed to: {current_database}")
                continue

            if lowered in ["databases", "show databases", "list databases"]:
                handle_database_list()
                continue

            if lowered in ["tables", "show tables", "list tables"]:
                handle_table_list(current_database)
                continue

            current_database = answer_question(question, current_database)

        except KeyboardInterrupt:
            print("\nBye.")
            break

        except requests.exceptions.ConnectionError as e:
            print("\nConnection error.")
            print("Check if Ollama and mysql-mcp-server are running.")
            print(str(e))

        except requests.exceptions.HTTPError as e:
            print("\nHTTP error.")
            print(str(e))

            if e.response is not None:
                print(e.response.text)

        except Exception as e:
            print("\nError:")
            print(str(e))


if __name__ == "__main__":
    main()
