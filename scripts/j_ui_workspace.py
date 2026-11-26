#!/usr/bin/env python3
"""Run the local J browser UI with workspace editor and terminal controls."""
from __future__ import annotations

import argparse
import ipaddress
import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.j_cli import DEFAULT_ENDPOINT, DEFAULT_MODEL, HarnessError, _default_system_prompt, call_model
from scripts.j_ui import MAX_BODY_BYTES, MAX_FILE_BYTES, _loopback_endpoint, make_handler
from http.server import ThreadingHTTPServer

LOGGER = logging.getLogger("j_ui_workspace")
MAX_COMMAND_LENGTH = 4_000
MAX_COMMAND_OUTPUT = 30_000
MAX_COMMAND_TIMEOUT = 120

WORKSPACE_PAGE = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="theme-color" content="#101114"><title>J · Local workspace</title>
<style>
:root{color-scheme:dark;--bg:#101114;--panel:#17181c;--panel2:#1d1f24;--line:#2b2d33;--text:#eeeae2;--muted:#9a9ba3;--accent:#d4a574;--green:#8bc49b;--red:#e58a83;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);height:100vh;overflow:hidden}button,input,textarea{font:inherit;color:inherit}button{cursor:pointer}.shell{height:100%;display:grid;grid-template-columns:250px minmax(0,1fr) 315px}.sidebar{background:#131417;border-right:1px solid var(--line);display:flex;flex-direction:column;padding:17px 13px;min-width:0}.brand{display:flex;align-items:center;gap:11px;padding:4px 7px 19px}.mark{width:32px;height:32px;border:1px solid #735b42;border-radius:10px;display:grid;place-items:center;color:var(--accent);font-family:Georgia,serif;font-size:19px}.brand-name{font-weight:650}.brand-sub,.muted{font-size:11px;color:var(--muted);margin-top:3px}.path{width:100%;background:#101114;border:1px solid var(--line);border-radius:8px;padding:8px;font-size:11px}.row{display:flex;gap:7px;align-items:center}.btn{border:1px solid var(--line);background:var(--panel2);border-radius:8px;padding:8px 10px;font-size:11px}.btn:hover{border-color:var(--accent)}.btn.primary{background:var(--accent);border-color:var(--accent);color:#17130f;font-weight:650}.btn:disabled{opacity:.5;cursor:not-allowed}.label{font-size:10px;text-transform:uppercase;letter-spacing:.14em;color:var(--muted);padding:19px 7px 8px}.file-list{overflow:auto;flex:1}.file-item{display:block;width:100%;background:transparent;border:0;text-align:left;border-radius:7px;padding:8px 9px;color:#ceccc6;font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.file-item:hover,.file-item.active{background:#24252a}.file-item.dir{color:var(--accent)}.main{display:flex;flex-direction:column;min-width:0}.topbar{height:56px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid var(--line);padding:0 18px;font-size:12px;color:var(--muted)}.model-select{background:var(--panel);border:1px solid var(--line);padding:7px 10px;border-radius:8px}.work{flex:1;min-height:0;display:grid;grid-template-rows:minmax(0,1fr) 245px}.editor{display:flex;flex-direction:column;min-height:0}.editorbar,.terminalbar{height:42px;display:flex;align-items:center;gap:8px;padding:0 13px;border-bottom:1px solid var(--line);font-size:11px;color:var(--muted)}.filename{flex:1;color:#ddd9d2;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.editor textarea{flex:1;width:100%;resize:none;background:#111216;border:0;outline:0;padding:16px;color:#e5e3dd;font:12px/1.65 ui-monospace,SFMono-Regular,Menlo,monospace;tab-size:4}.terminal{display:flex;flex-direction:column;border-top:1px solid var(--line);min-height:0;background:#121316}.terminal-out{flex:1;overflow:auto;white-space:pre-wrap;overflow-wrap:anywhere;padding:10px 13px;color:#d4d1cb;font:11px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace}.terminal-form{display:flex;gap:8px;padding:9px;border-top:1px solid var(--line)}.terminal-form input{flex:1;min-width:0;background:#0e0f12;border:1px solid var(--line);border-radius:7px;padding:9px;font:11px ui-monospace,monospace;outline:0}.right{border-left:1px solid var(--line);background:#131417;display:flex;flex-direction:column;min-height:0}.chat-head{padding:16px;border-bottom:1px solid var(--line)}.chat-head strong{font-size:13px}.status{font-size:10px;color:var(--muted);margin-top:6px}.messages{flex:1;overflow:auto;padding:16px 13px}.msg{font-size:12px;line-height:1.65;white-space:pre-wrap;overflow-wrap:anywhere;margin-bottom:17px}.msg .role{font-size:9px;letter-spacing:.12em;text-transform:uppercase;color:var(--accent);margin-bottom:5px}.msg.user .role{color:var(--muted)}.compose{padding:10px;border-top:1px solid var(--line)}.compose textarea{width:100%;resize:vertical;min-height:72px;max-height:180px;background:#1a1b20;border:1px solid var(--line);border-radius:9px;padding:10px;font-size:12px;outline:0}.compose .row{justify-content:space-between;margin-top:8px}.foot{font-size:9px;color:var(--muted)}.danger-note{font-size:10px;color:#c7a784;line-height:1.55;padding:10px 13px;border-top:1px solid var(--line)}.banner{position:fixed;left:260px;right:315px;top:56px;background:#241d17;color:#d7b58c;padding:7px 12px;font-size:10px;z-index:2}.hidden{display:none!important}.newfile{margin-top:8px}.error{color:var(--red)}@media(max-width:1050px){.shell{grid-template-columns:210px minmax(0,1fr)}.right{display:none}.banner{right:0}}@media(max-width:650px){body{overflow:auto}.shell{grid-template-columns:1fr;height:100dvh}.sidebar{display:none}.work{grid-template-rows:minmax(0,1fr) 210px}.banner{left:0}.topbar{padding:0 10px}}
</style></head>
<body><div class="shell">
<aside class="sidebar"><div class="brand"><div class="mark">J</div><div><div class="brand-name">J workspace</div><div class="brand-sub">Private · Local · Yours</div></div></div><div class="row"><input id="workspacePath" class="path" aria-label="Workspace root" placeholder="Workspace root"><button id="refreshFiles" class="btn" data-testid="refresh-files-btn">Load</button></div><div class="label">Workspace files</div><div id="files" class="file-list" data-testid="workspace-file-list"></div><div class="label">Create file</div><div class="row newfile"><input id="newPath" class="path" aria-label="New file path" placeholder="relative/path.txt"></div><button id="createFile" class="btn" data-testid="create-file-btn" style="margin-top:7px">New file</button></aside>
<main class="main"><header class="topbar"><span id="workspaceLabel">LOCAL WORKSPACE</span><select id="model" class="model-select" data-testid="model-select" aria-label="Model"><option>qwen2.5:7b</option></select></header><div class="work"><section class="editor"><div class="editorbar"><span id="currentFile" class="filename">No file open</span><button id="saveFile" class="btn primary" data-testid="save-file-btn" disabled>Save file</button></div><textarea id="editor" data-testid="file-editor" spellcheck="false" placeholder="Choose a file from the workspace tree, or create one."></textarea></section><section class="terminal"><div class="terminalbar"><span style="color:var(--accent)">LOCAL TERMINAL</span><span class="muted">cwd: workspace root</span><button id="clearTerminal" class="btn" data-testid="clear-terminal-btn" style="margin-left:auto">Clear</button></div><pre id="terminalOutput" class="terminal-out" data-testid="terminal-output">Shell access is enabled for this local session. Commands run with your OS user permissions.</pre><form id="terminalForm" class="terminal-form"><input id="command" data-testid="shell-command-input" autocomplete="off" placeholder="Enter a shell command…"><button id="runCommand" class="btn primary" data-testid="run-shell-btn">Run</button></form></section></div></main>
<aside class="right"><div class="chat-head"><strong>J · Assistant</strong><div id="runtime" class="status">Checking local model…</div></div><div id="messages" class="messages" data-testid="chat-messages" aria-live="polite"></div><form id="chatForm" class="compose"><textarea id="prompt" data-testid="chat-input" placeholder="Ask J to reason about your workspace…"></textarea><div class="row"><span class="foot">Local model · workspace context stays local</span><button id="send" class="btn primary" data-testid="send-message-btn">Send</button></div></form><div class="danger-note">Files are edited in the center pane. Shell commands run locally with your account's permissions. Review commands before running.</div></aside></div>
<div class="banner">Local shell + write access enabled. Review changes and commands before running; the process has your OS account permissions.</div>
<script>
const $=id=>document.getElementById(id);let root="";let openPath="";let chat=[];let selectedModel="qwen2.5:7b";function esc(value){return String(value).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]))}async function api(url,options={}){const response=await fetch(url,options);const body=await response.json();if(!response.ok)throw new Error(body.error||`HTTP ${response.status}`);return body}async function loadFiles(path=""){try{const data=await api("/api/files"+(path?"?path="+encodeURIComponent(path):""));root=data.root;$('workspaceLabel').textContent="WORKSPACE · "+root;$('workspacePath').value=root;const list=$('files');list.replaceChildren();for(const item of data.files){const button=document.createElement('button');button.className="file-item "+(item.is_dir?"dir":"")+(item.path===openPath?" active":"");button.dataset.testid="workspace-file-item";button.textContent=(item.is_dir?"▸ ":"  ")+item.name;button.title=item.path;button.onclick=()=>item.is_dir?loadFiles(item.path):openFile(item.path);list.append(button)}}catch(error){terminalLine("File browser error: "+error.message,true)}}async function openFile(path){try{const data=await api("/api/file?path="+encodeURIComponent(path));openPath=data.path;$('currentFile').textContent=data.path;$('editor').value=data.content;$('saveFile').disabled=false;await loadFiles(root)}catch(error){terminalLine("Open failed: "+error.message,true)}}async function saveFile(){if(!openPath)return;try{await api("/api/file/write",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({path:openPath,content:$('editor').value})});terminalLine("Saved "+openPath);$('saveFile').textContent="Saved";setTimeout(()=>{$('saveFile').textContent="Save file"},900)}catch(error){terminalLine("Save failed: "+error.message,true)}}function terminalLine(text,error=false){const output=$('terminalOutput');output.textContent+=(output.textContent?"\n":"")+(error?"ERROR: ":"")+text;output.scrollTop=output.scrollHeight}function addMessage(role,text){const box=document.createElement('div');box.className="msg "+role;box.dataset.testid=role+"-message";box.innerHTML=`<div class="role">${role==="user"?"You":"J"}</div><div>${esc(text)}</div>`;$('messages').append(box);$('messages').scrollTop=$('messages').scrollHeight}async function sendChat(text){if(!text.trim())return;chat.push({role:"user",content:text.trim()});addMessage("user",text.trim());$('prompt').value="";$('send').disabled=true;try{const result=await api("/api/chat",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({messages:chat,model:selectedModel})});chat.push({role:"assistant",content:result.reply});addMessage("assistant",result.reply)}catch(error){addMessage("assistant","Request failed: "+error.message)}finally{$('send').disabled=false;$('prompt').focus()}}$('refreshFiles').onclick=()=>loadFiles($('workspacePath').value.trim());$('saveFile').onclick=saveFile;$('editor').addEventListener('input',()=>{$('saveFile').textContent="Save file"});$('createFile').onclick=async()=>{const path=$('newPath').value.trim();if(!path)return;try{await api("/api/file/write",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({path,content:""})});$('newPath').value="";await loadFiles(root);await openFile(path);terminalLine("Created "+path)}catch(error){terminalLine("Create failed: "+error.message,true)}};$('terminalForm').onsubmit=async event=>{event.preventDefault();const command=$('command').value.trim();if(!command)return;terminalLine("$ "+command);$('command').value="";$('runCommand').disabled=true;try{const result=await api("/api/command",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({command})});terminalLine(result.output||`(exit ${result.exit_code})`);terminalLine("exit code: "+result.exit_code)}catch(error){terminalLine(error.message,true)}finally{$('runCommand').disabled=false;$('command').focus()}};$('clearTerminal').onclick=()=>$('terminalOutput').textContent="";$('chatForm').onsubmit=event=>{event.preventDefault();sendChat($('prompt').value)};$('prompt').onkeydown=event=>{if(event.key==="Enter"&&!event.shiftKey){event.preventDefault();$('chatForm').requestSubmit()}};async function init(){try{const models=await api("/api/models");$('runtime').textContent="Model endpoint ready · "+models.endpoint;if(models.models?.length){$('model').replaceChildren(...models.models.map(name=>{const option=document.createElement('option');option.value=name;option.textContent=name;return option}))}selectedModel=models.default_model||$('model').value;$('model').value=selectedModel;$('model').onchange=()=>selectedModel=$('model').value}catch(error){$('runtime').textContent="Model unavailable · "+error.message}await loadFiles()}init();
</script></body></html>'''


def _local_request_allowed(handler: BaseHTTPRequestHandler) -> bool:
    try:
        peer = ipaddress.ip_address(handler.client_address[0])
    except ValueError:
        return False
    if not peer.is_loopback:
        return False

    host = urlparse(f"//{handler.headers.get('Host', '')}").hostname
    if host not in {"localhost", "127.0.0.1", "::1"}:
        return False
    origin = handler.headers.get("Origin")
    if origin:
        parsed_origin = urlparse(origin)
        origin_host = (parsed_origin.hostname or "").lower()
        origin_port = parsed_origin.port or (443 if parsed_origin.scheme == "https" else 80)
        host_header = handler.headers.get("Host", "")
        host_parts = urlparse(f"//{host_header}")
        host_port = host_parts.port or 80
        if origin_host not in {"localhost", "127.0.0.1", "::1"} or origin_port != host_port:
            return False
    return True


def _workspace_file(root: Path, requested: str) -> Path:
    if not requested:
        raise HarnessError("file path is required")
    candidate = (root / requested).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise HarnessError("workspace path escapes the configured workspace root") from exc
    return candidate


def make_workspace_handler(
    endpoint: str,
    model: str,
    api_key: str,
    system_prompt: str,
    workspace: Path,
    timeout: int,
) -> type:
    base_handler = make_handler(endpoint, model, api_key, system_prompt, workspace, timeout, call_model_fn=call_model)
    root = workspace.resolve()

    class WorkspaceHandler(base_handler):
        def do_GET(self) -> None:
            if urlparse(self.path).path == "/":
                self._send(200, WORKSPACE_PAGE.encode("utf-8"), "text/html; charset=utf-8")
                return
            if urlparse(self.path).path == "/api/files":
                self._get_workspace_listing(parse_qs(urlparse(self.path).query).get("path", [""])[0])
                return
            super().do_GET()

        def _get_workspace_listing(self, requested: str) -> None:
            try:
                directory = _workspace_file(root, requested) if requested else root
                if not directory.is_dir():
                    raise HarnessError("requested workspace path is not a directory")
                items = []
                for item in sorted(directory.iterdir(), key=lambda entry: (not entry.is_dir(), entry.name.lower())):
                    resolved = item.resolve()
                    try:
                        relative = resolved.relative_to(root)
                    except ValueError:
                        continue
                    items.append({"name": item.name, "path": str(relative), "is_dir": item.is_dir()})
                self._json(200, {"root": str(root), "files": items})
            except (OSError, HarnessError) as exc:
                self._json(400, {"error": str(exc)})

        def do_POST(self) -> None:
            route = urlparse(self.path).path
            if route not in {"/api/command", "/api/file/write"}:
                super().do_POST()
                return
            if not _local_request_allowed(self):
                self._json(403, {"error": "Workspace actions require a same-origin loopback request"})
                return
            try:
                payload = self._body()
                if route == "/api/command":
                    self._run_command(payload)
                else:
                    self._write_file(payload)
            except HarnessError as exc:
                self._json(400, {"error": str(exc)})

        def _write_file(self, payload: dict[str, Any]) -> None:
            path = _workspace_file(root, str(payload.get("path", "")))
            content = payload.get("content")
            if not isinstance(content, str):
                raise HarnessError("file content must be text")
            encoded = content.encode("utf-8")
            if len(encoded) > MAX_FILE_BYTES:
                raise HarnessError("file content exceeds the 200 KB write limit")
            path.parent.mkdir(parents=True, exist_ok=True)
            resolved_parent = path.parent.resolve()
            try:
                resolved_parent.relative_to(root)
            except ValueError as exc:
                raise HarnessError("workspace path escapes the configured workspace root") from exc
            path.write_text(content, encoding="utf-8")
            self._json(200, {"ok": True, "path": str(path.relative_to(root)), "bytes_written": len(encoded)})

        def _run_command(self, payload: dict[str, Any]) -> None:
            command = payload.get("command")
            if not isinstance(command, str) or not command.strip():
                raise HarnessError("command must be non-empty text")
            if len(command) > MAX_COMMAND_LENGTH:
                raise HarnessError(f"command exceeds the {MAX_COMMAND_LENGTH}-character limit")
            try:
                result = subprocess.run(
                    command,
                    shell=True,
                    cwd=root,
                    capture_output=True,
                    text=True,
                    timeout=min(timeout, MAX_COMMAND_TIMEOUT),
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                stdout = exc.stdout.decode("utf-8", errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
                stderr = exc.stderr.decode("utf-8", errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
                output = (stdout + ("\n" if stdout and stderr else "") + stderr)[:MAX_COMMAND_OUTPUT]
                self._json(408, {"error": "command timed out", "output": output, "exit_code": None})
                return
            output = result.stdout + ("\n" if result.stdout and result.stderr else "") + result.stderr
            self._json(200, {"output": output[:MAX_COMMAND_OUTPUT], "exit_code": result.returncode})

    return WorkspaceHandler


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run J's local browser workspace with a file editor and shell.")
    parser.add_argument("--host", default="127.0.0.1", help="interface to bind; loopback only")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--endpoint", default=os.environ.get("J_CLI_ENDPOINT", DEFAULT_ENDPOINT))
    parser.add_argument("--model", default=os.environ.get("J_CLI_MODEL", DEFAULT_MODEL))
    parser.add_argument("--api-key", default=os.environ.get("J_CLI_API_KEY", ""))
    parser.add_argument("--system-prompt", type=Path, default=_default_system_prompt())
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args(argv)
    if args.port < 1 or args.port > 65535:
        parser.error("--port must be between 1 and 65535")
    if args.timeout < 1:
        parser.error("--timeout must be positive")
    if args.host not in {"127.0.0.1", "localhost", "::1"}:
        parser.error("the UI server must bind to loopback only")
    try:
        endpoint = _loopback_endpoint(args.endpoint)
        workspace = args.workspace.resolve(strict=True)
        if not workspace.is_dir():
            raise HarnessError("workspace root must be a directory")
        prompt = args.system_prompt.read_text(encoding="utf-8") if args.system_prompt else ""
        handler = make_workspace_handler(endpoint, args.model, args.api_key, prompt, workspace, args.timeout)
    except (OSError, HarnessError) as exc:
        parser.error(str(exc))
    server = ThreadingHTTPServer((args.host, args.port), handler)
    server.daemon_threads = True
    LOGGER.info("J local workspace ready at http://%s:%s", args.host, args.port)
    LOGGER.info("Workspace root: %s", workspace)
    LOGGER.warning("The local shell runs with your OS account permissions; review commands before execution.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        LOGGER.info("Shutting down local workspace")
    finally:
        server.shutdown()
        server.server_close()
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    raise SystemExit(main())
