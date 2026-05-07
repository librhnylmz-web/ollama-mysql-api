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

    function addSqlApproval(question, sql, botMessage) {
      const div = document.createElement("div");
      div.className = "sql-approval";

      const title = document.createElement("div");
      title.className = "sql-approval-title";
      title.textContent = "Generated SQL. Review it before running:";

      const pre = document.createElement("pre");
      pre.textContent = sql;

      const button = document.createElement("button");
      button.className = "run-query-btn";
      button.textContent = "Run query";

      button.onclick = async function() {
      button.disabled = true;
      button.textContent = "Running...";
      await runApprovedQuery(question, sql, botMessage);
    };

      div.appendChild(title);
      div.appendChild(pre);
      div.appendChild(button);

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
  const botMessage = addLine("dbbot", "Thinking...", "bot");

  try {
    const response = await fetch("/preview_sql", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ question })
    });

    const data = await response.json();

    if (!response.ok || !data.success) {
      botMessage.textContent = "Error: " + (data.error || "Request failed.");

      if (data.sql) {
        addSql(data.sql);
      }

      return;
    }

    if (data.needs_sql === false) {
      botMessage.textContent = data.answer || "I could not answer this from the current context.";
      chat.scrollTop = chat.scrollHeight;
      return;
    }

    botMessage.textContent = "I generated a SQL query. Please review it before running.";
    addSqlApproval(question, data.sql, botMessage);

  } catch (err) {
    botMessage.textContent = "Error: " + err;
  } finally {
    sendBtn.disabled = false;
    input.disabled = false;
    input.focus();
  }
}

async function runApprovedQuery(question, sql, botMessage) {
  sendBtn.disabled = true;
  input.disabled = true;
  botMessage.textContent = "Running approved query...";

  try {
    const response = await fetch("/ask_stream", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ question, sql })
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

      const lines = buffer.split("\n");
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
