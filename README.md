# Ollama MySQL API Chatbot

A local Flask chatbot that uses Ollama to generate SQL queries and reads data from a MySQL database through a mysql-mcp-server HTTP API.

The project is designed as a small local demo for experimenting with natural language database queries, local LLMs and a simple web-based chat interface.

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
- HTML, CSS and JavaScript

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