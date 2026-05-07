# Ollama MySQL MCP Chatbot

A small local AI lab that connects Ollama, MySQL, mysql-mcp-server, and a Flask chatbot.

The goal of this project is to ask natural language questions over a local MySQL database. The language model generates SQL, the MySQL MCP server runs the query through a read-only database user, and the Flask app shows the answer in a simple browser UI.

## What this project does

- Runs a local chatbot with Flask
- Uses Ollama as the local LLM provider
- Uses mysql-mcp-server as the MySQL access layer
- Sends generated SQL to the MCP server HTTP API
- Uses Markdown files to provide prompt instructions and business context
- Keeps database credentials outside the application code

## Architecture

```text
User
  ↓
Flask Chatbot app.py
  ↓
Ollama local LLM
  ↓
mysql-mcp-server HTTP API
  ↓
MySQL demo_ai database
```

## Project structure

```text
ollama-mysql-api/
├── app.py
├── ask_db.py
├── config.json
├── prompts/
│   ├── sql_generation.md
│   └── answer_summary.md
└── context/
    └── demo_ai.md
```

## Main components

### app.py

Runs the Flask web chatbot.

### ask_db.py

Runs the same flow from the terminal as a local shell.

### config.json

Stores local configuration such as:

- Ollama API URL
- MCP API URL
- model name
- default database
- history size
- schema table limit

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

### prompts/

Contains prompt templates used by the application.

- `sql_generation.md` tells the model how to generate safe SQL
- `answer_summary.md` tells the model how to summarize database results

### context/

Contains business context for the database.

For example, `context/demo_ai.md` explains what each table means. This helps the model understand tables with unclear names such as `z9_kx_txn`.

## Example questions

```text
How many customers do I have?
Who bought Wireless Mouse?
What is my total revenue?
Which product sold the most?
Who is my top buyer?
```

## Requirements

- Ubuntu or WSL
- Python 3
- Docker
- MySQL
- Ollama
- mysql-mcp-server Docker image

## Python dependencies

Python dependencies are listed in `requirements.txt`.

```text
flask
requests
```

Install them with:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Running the Flask chatbot

Start Ollama:

```bash
ollama serve
```

Make sure the model exists:

```bash
ollama pull llama3.2:3b
```

Start mysql-mcp-server separately with your own MySQL DSN.

Then run the app:

```bash
cd ollama-mysql-api
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open the browser:

```text
http://127.0.0.1:5000
```

## Running the terminal shell

```bash
cd ollama-mysql-api
source .venv/bin/activate
python ask_db.py
```

## Security notes

This project is intended as a local lab.

Recommended safety practices:

- Use a read-only MySQL user
- Do not commit database passwords
- Do not expose mysql-mcp-server directly to the internet
- Keep Ollama and the Flask app local unless properly secured
- Use query timeout and row limits on the MCP server side

## Why Markdown context files?

The database schema tells the model what tables and columns exist.

The Markdown context file explains what those tables mean.

For example, a table named `z9_kx_txn` is not obvious to a language model. The context file can explain that it stores product sales transactions.

This creates a simple semantic layer for the AI assistant.

## Status

This is an experimental local AI database assistant project.
