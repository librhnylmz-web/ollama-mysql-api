# Ollama MySQL API Chatbot

A local Flask chatbot that uses Ollama to generate SQL queries and reads data from a MySQL database through a mysql-mcp-server HTTP API.

The project is designed as a small local demo for experimenting with natural language database queries, local LLMs, and a simple web-based chat interface.

## What it does

- Runs a Flask web chatbot on `http://127.0.0.1:5000`
- Uses a local Ollama model, currently `llama3.2:3b`
- Generates SQL from natural language questions
- Sends safe read-only SQL queries to mysql-mcp-server
- Reads data from the `demo_ai` MySQL database
- Streams answers back to the browser with NDJSON
- Shows system health status in the UI
- Shows database schema information in the sidebar
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
- NDJSON streaming
- Ollama requests
- MCP API requests
- SQL safety checks
- Health check endpoint
- Schema endpoint

### `ask_db.py`

Terminal-based version of the chatbot.

Useful for testing the same logic without the web UI.

### `config.json`

Main configuration file.

Example:

```json
{
  "ollama_url": "http://localhost:11434/api/generate",
  "mcp_api_base": "http://localhost:9306/api",
  "model": "llama3.2:3b",
  "default_database": "demo_ai",
  "max_history_items": 5,
  "max_schema_tables": 10
}
```

### `templates/index.html`

The main Flask HTML template.

### `static/css/app.css`

Styles for the IRC-style chatbot UI.

### `static/js/app.js`

Browser-side JavaScript.

It handles:

- Sending questions
- Reading NDJSON stream responses
- Updating the chat window
- Loading health status
- Loading schema information

### `prompts/sql_generation.md`

Prompt used to generate SQL from a user question.

### `prompts/answer_summary.md`

Prompt used to summarize database results into a human-readable answer.

### `context/demo_ai.md`

Database context for the demo database.

## Requirements

- Python 3
- Docker
- MySQL
- Ollama
- A pulled Ollama model

Example:

```bash
ollama pull llama3.2:3b
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

The project currently expects:

```text
llama3.2:3b
```

If you want to use another model, update `config.json`.

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
    "model": "llama3.2:3b"
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

## Schema endpoint

The project includes a schema endpoint:

```text
http://127.0.0.1:5000/schema
```

It returns the available tables and columns from the configured database.

The web UI uses this endpoint to show the schema browser in the sidebar.

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
Who bought Wireless Mouse?
What is the total revenue?
Show me the latest orders.
Which customer spent the most money?
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
- The current UI is single-user and does not persist chat history
- The app expects Ollama and mysql-mcp-server to already be running

## Suggested next improvements

- Show generated SQL in the UI
- Show raw database result in a collapsible panel
- Add query history in the sidebar
- Add database selector
- Add `.env` support
- Add Docker Compose for MySQL and mysql-mcp-server
- Add tests for SQL safety checks

## License

MIT