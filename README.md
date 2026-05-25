# Before-workshop checklist

A self-serve checklist for students attending the Hardening MCP Servers workshop. Go top to bottom; tick each box as you complete it. You should be done in **under 30 minutes** if your machine already has a recent Python and a working terminal.

Total: 7 steps. The workshop itself is not about installing MCP servers. Once you finish Step 5 you can be confident that you're ready on workshop day.

---

## Step 0 — Pre-read (~30 min the night before)

We'll touch all of these during the workshop. Skimming them ahead of time means you can spend the workshop arguing with the material instead of parsing it for the first time. You do not need to memorize anything.

- [ ] [MCP specification 2025-11-25](https://modelcontextprotocol.io/specification/latest) — focus on the [Security Best Practices](https://modelcontextprotocol.io/specification/latest/basic/security_best_practices) and [Authorization](https://modelcontextprotocol.io/specification/latest/basic/authorization) pages.
- [ ] [OWASP MCP Top 10](https://owasp.org/www-project-mcp-top-10/) — read the top-level taxonomy. You do not need to memorize the IDs; recognising the categories (tool poisoning, token passthrough, prompt injection, etc.) is enough.

---

## Step 1 — Fork and clone

- [ ] Fork the upstream `mcp-security-workshop` repo on GitHub.
- [ ] **Rename your fork** on GitHub to `mcp-security-workshop-<firstname-lastname>` (e.g. `mcp-security-workshop-jane-doe`). Your peers will use this naming to distinguish forks during interactive exercises.
- [ ] Clone your renamed fork and set a shell variable you can reuse below:
  ```bash
  git clone https://github.com/<your-handle>/mcp-security-workshop-<firstname-lastname>.git
  cd mcp-security-workshop-<firstname-lastname>
  export WORKSHOP_DIR="$(pwd)"
  ```

---

## Step 2 — Local environment

- [ ] Confirm Python 3.11 or newer is installed:
  ```bash
  python3 --version    # need >= 3.11
  ```
  If you need to install it:
  ```bash
  # macOS:
  brew install python@3.11
  # Linux (pyenv):
  pyenv install 3.11.9 && pyenv global 3.11.9
  ```
- [ ] Install `uv` (the Python package/venv manager this repo uses):
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  exec $SHELL          # reload PATH so `uv` is on it
  uv --version         # sanity check — should print a version number
  ```
- [ ] Sync dependencies (creates a project-local virtualenv and installs everything):
  ```bash
  cd "$WORKSHOP_DIR"
  uv sync
  ```

---

## Step 3 — Dependency sanity check

- [ ] Verify the core libraries actually import cleanly:
  ```bash
  uv run python -c "import mcp, httpx, jwt, yaml, starlette; print('ok')"
  ```
  Expected output: `ok`. Anything else means `uv sync` did not finish — re-run it and re-check.

---

## Step 4 — Register MCP servers in your client

Pick **one** client — Claude Code or Cursor (though Claude is recommended for more ease of use!  The facilitator will be using it) — and use its block below. The workshop is not about wiring up MCP servers, so we do this once now and leave it connected for the whole day. There is no remove/re-add cycle.

### Claude Code

- [ ] From the repo root, register all three servers:

  ```bash
  cd "$WORKSHOP_DIR"
  claude mcp add acmeops           -- uv run python -m acmeops_server --transport stdio
  claude mcp add summarizer_server -- uv run python -m summarizer_server
  ```

- [ ] Confirm all three are connected:
  ```bash
  claude mcp list
  # All entries should show "Connected" (or a green check, depending on your version)
  ```

### Cursor

- [ ] Open `~/.cursor/mcp.json` (create it if it doesn't exist) and add the following block. 
  ```json
  {
    "mcpServers": {
      "acmeops": {
        "command": "/absolute/path/to/mcp-security-workshop-<firstname-lastname>/.venv/bin/python",
        "args": ["-m", "acmeops_server", "--transport", "stdio"]
      },
      "summarizer_server": {
        "command": "/absolute/path/to/mcp-security-workshop-<firstname-lastname>/.venv/bin/python",
        "args": ["-m", "summarizer_server"]
      }
    }
  }
  ```
- [ ] Restart Cursor. Open Settings → Features → MCP. Each of the entries should show a green dot.

---

## Step 5 — Smoke-test each server (list one tool)

In your client's chat, send the prompt below once per server. Confirm that one of the expected tool names appears in the response. Don't worry about behaviour here as we'll do that during the workshop, only confirm the client can reach the server and read its tool list.

> "What tools does the `<server-name>` MCP server expose?"

Expected tools per server (any match is a pass):

- [ ] `acmeops` — `read_customer_note`, `draft_email`, `run_db_query`, etc.
- [ ] `summarizer_server` — `summarize`

If a server shows no tools or fails to connect, debug it now. Don't wait until T-30 on workshop day.

---

## Step 6 — HTTP smoke-test the fake authz server

This is **not** an MCP server. It's a local OAuth 2.1 authorization server that you may get to use in one demo. Don't register it in your MCP client; just confirm that it runs.

- [ ] Start it, hit one of the "well-known" endpoints, then stop it:
  ```bash
  cd "$WORKSHOP_DIR"
  uv run python -m fake_authz_server &
  sleep 2
  curl -s http://localhost:9000/.well-known/oauth-authorization-server | python -m json.tool | head -10
  # Expected: a JSON object whose "issuer" field is "http://localhost:9000"
  kill %1
  ```

---

## Step 7 — Final pre-flight

- [ ] `claude mcp list` (or the Cursor MCP panel) shows all six servers connected.
- [ ] All smoke-test prompts in Step 5 returned the expected tool names.
- [ ] `uv run python -c "import mcp; print('ok')"` prints `ok`.
- [ ] You've at least skimmed the MCP 2025-11-25 spec's Security Best Practices section.

If every box is ticked, you're set! See you on workshop day!
