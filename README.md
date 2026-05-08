# Ollama MySQL API Chatbot

A local Flask chatbot that uses Ollama to generate SQL queries and read data from a MySQL database through a mysql-mcp-server HTTP API.

The project is designed as a local demo for experimenting with natural language database queries, local LLMs, SQL review workflows, and database context discovery.

## What it does

- Runs a Flask web chatbot on `http://127.0.0.1:5000`
- Uses a local Ollama model
- Generates SQL from natural language questions
- Shows generated SQL before execution
- Runs SQL only after user approval
- Sends safe read-only SQL queries to mysql-mcp-server
- Reads data from the configured MySQL database
- Streams answers back to the browser with NDJSON
- Answers in the same language as the user's question
- Detects follow-up questions before generating SQL
- Shows system health status in the UI
- Shows database schema information in the sidebar
- Supports chat-based database context discovery
- Includes a terminal version with `ask_db.py`

## Stack

- Ubuntu / WSL
- Python
- Flask
- Ollama
- MySQL
- mysql-mcp-server Docker container
- HTML, CSS, and JavaScript

## Project structure

```text
ollama-mysql-api
├── app.py
├── ask_db.py
├── config.json
├── requirements.txt
├── README.md
├── context
│   └── demo_ai.md
├── docs
│   └── index.html
├── prompts
│   ├── answer_summary.md
│   ├── followup_answer.md
│   ├── intent_detection.md
│   └── sql_generation.md
├── static
│   ├── css
│   │   └── app.css
│   └── js
│       └── app.js
└── templates
    └── index.html
```

## Main files

### `app.py`

The Flask web application.

It handles:

- Web UI route
- Chat API
- SQL preview endpoint
- SQL approval flow
- NDJSON streaming
- Ollama requests
- MCP API requests
- SQL safety checks
- Intent detection
- Follow-up answers
- Health check endpoint
- Schema endpoint
- Context discovery endpoints

### `ask_db.py`

Terminal-based version of the chatbot.

Useful for testing the same database assistant logic without the web UI.

### `config.json`

Main configuration file.

Example:

```json
{
  "ollama_url": "http://localhost:11434/api/generate",
  "mcp_api_base": "http://localhost:9306/api",
  "model": "qwen2.5:3b",
  "default_database": "demo_ai",
  "max_history_items": 5,
  "max_schema_tables": 10
}
```

You can use another local Ollama model by changing the `model` value.

### `templates/index.html`

The main Flask HTML template.

### `static/css/app.css`

Styles for the IRC-style chatbot UI.

### `static/js/app.js`

Browser-side JavaScript.

It handles:

- Sending questions
- SQL preview approval
- Running approved queries
- Reading NDJSON stream responses
- Updating the chat window
- Loading health status
- Loading schema information
- Running chat-based context discovery

### `prompts/sql_generation.md`

Prompt used to generate SQL from a user question.

### `prompts/answer_summary.md`

Prompt used to summarize database results into a human-readable answer.

### `prompts/intent_detection.md`

Prompt used to decide whether a user question requires a new SQL query.

This helps avoid generating SQL for follow-up questions like:

```text
Can you explain this result?
Can you make this shorter?
What does this mean?
```

### `prompts/followup_answer.md`

Prompt used to answer follow-up questions without generating a new SQL query.

### `context/demo_ai.md`

Business context for the demo database.

The chatbot uses this file to better understand table meanings, business terms, and how to generate better SQL.

## Requirements

- Python 3
- Docker
- MySQL
- Ollama
- A pulled Ollama model

Example:

```bash
ollama pull qwen2.5:3b
```

Other small models can also be used, for example:

```bash
ollama pull llama3.2:3b
ollama pull gemma3:4b
```

## Python setup

Create and activate a virtual environment:

```bash
cd ollama-mysql-api

python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## Ollama setup

Start Ollama:

```bash
ollama serve
```

Check available models:

```bash
ollama list
```

Update `config.json` if you want to use a different model.

## MySQL MCP server

The Flask app expects mysql-mcp-server to be available over HTTP at:

```text
http://localhost:9306/api
```

The app uses the `/api/query` endpoint to execute database queries.

## Running the Flask app

Activate the virtual environment:

```bash
cd ollama-mysql-api
source .venv/bin/activate
```

Run the app:

```bash
python app.py
```

Open the UI:

```text
http://127.0.0.1:5000
```

## Running the terminal chatbot

```bash
cd ollama-mysql-api
source .venv/bin/activate

python ask_db.py
```

## SQL approval flow

The web UI does not run model-generated SQL immediately.

The flow is:

```text
User asks a question
↓
App detects whether SQL is needed
↓
If SQL is needed, the model generates SQL
↓
The SQL is shown in the UI
↓
User reviews the SQL
↓
User clicks Run query
↓
The query is executed
↓
The result is summarized by the model
```

This keeps the demo safer and more transparent.

## Follow-up handling

The app includes an intent detection step before SQL generation.

If the user asks a normal database question, SQL is generated.

Example:

```text
How many customers are there?
How many customers are there?
Which customer spent the most money?
```

If the user asks a follow-up question, SQL is not generated.

Example:

```text
Can you explain this result?
Can you make this shorter?
What does this result mean?
```

The app answers these questions using recent conversation history.

## Language behavior

The assistant is instructed to answer in the same language as the user's question.

Examples:

```text
User: How many customers are there?

User: How many customers are there?
Assistant: There are 3 customers.
```

## Health check

The project includes a health endpoint:

```text
http://127.0.0.1:5000/health
```

It checks:

- Flask app
- Ollama API
- MCP API
- Default database
- Available table count

Example response:

```json
{
  "status": "ok",
  "flask": {
    "status": "ok"
  },
  "ollama": {
    "status": "ok",
    "model": "qwen2.5:3b"
  },
  "mcp": {
    "status": "ok",
    "database": "demo_ai",
    "table_count": 4,
    "tables": [
      "customers",
      "products",
      "orders",
      "order_items"
    ]
  }
}
```

The UI refreshes health status periodically.

## Schema endpoint

The project includes a schema endpoint:

```text
http://127.0.0.1:5000/schema
```

It returns the available tables and columns from the configured database.

The web UI uses this endpoint to show the schema browser in the sidebar.

## Context discovery

The app supports chat-based database context discovery.

Use this command in the chat UI:

```text
/discover table_name
```

Example:

```text
/discover support_tickets
```

The app will:

```text
1. Read the table schema
2. Read a few sample rows
3. Ask the local model to generate a markdown context suggestion
4. Show the suggestion in the chat UI
5. Wait for user approval
6. Append the approved context to the database context file
```

This helps the assistant understand newly added tables without manually editing the context file every time.

The model does not save context automatically. The user must approve the generated context first.

## Context discovery endpoints

The UI uses these endpoints internally:

```text
POST /discover_context
POST /approve_context
```

`/discover_context` generates a markdown suggestion.

`/approve_context` appends the approved markdown to the context file.

## SQL safety

The app is designed to run read-only queries only.

Allowed SQL prefixes include:

```text
SELECT
SHOW
DESCRIBE
DESC
EXPLAIN
```

Blocked operations include:

```text
INSERT
UPDATE
DELETE
DROP
ALTER
TRUNCATE
CREATE
REPLACE
GRANT
REVOKE
SET
USE
CALL
LOAD
```

The app also blocks common risky patterns such as:

```text
multiple statements
SQL comments
information_schema
performance_schema
mysql.
sys.
load_file
get_lock
sleep
benchmark
```

This is still a local demo project. Do not expose it directly to the public internet without adding stronger authentication, authorization, rate limiting, and database-level permissions.

## Streaming

The browser chat uses NDJSON streaming instead of SSE.

Each response is streamed line by line from Flask to the browser. This keeps the UI responsive while the model is generating the final answer.

## Example questions

```text
How many customers are there?
How many customers are there?
Who bought Wireless Mouse?
What is the total revenue?
Show me the latest orders.
Which customer spent the most money?
Can you explain this more briefly?
What does this result mean?
```

## Example context discovery command

```text
/discover support_tickets
```

After approving the generated context, you can ask questions like:

```text
How many open support tickets are there?
How many open support tickets are there?
Which team has the most high priority tickets?
```

## Development notes

Run syntax checks:

```bash
python3 -m py_compile app.py ask_db.py
```

Check Git status:

```bash
git status
```

View changes:

```bash
git diff
```

## GitHub Pages documentation

The `docs/index.html` file can be used for a simple GitHub Pages landing page.

It is separate from the Flask web UI.

## Current limitations

- The project is intended for local demo usage
- SQL safety is application-level and should not replace database permissions
- The schema parser is basic
- The current UI is single-user
- Chat history is kept in memory only
- Context discovery uses sample rows and may need user review
- The app expects Ollama and mysql-mcp-server to already be running

## Suggested next improvements

- Show raw database results in a collapsible panel
- Add query history in the sidebar
- Add database selector
- Add `.env` support
- Add Docker Compose for MySQL and mysql-mcp-server
- Add tests for SQL safety checks
- Add duplicate detection before appending discovered context
- Add UI controls for context discovery instead of slash commands

## License

MIT
