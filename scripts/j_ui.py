#!/usr/bin/env python3
"""Serve the local J chat UI and a loopback-only model/workspace API."""
from __future__ import annotations

import argparse
import json
import logging
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
from urllib.request import Request, urlopen

from scripts.j_cli import DEFAULT_ENDPOINT, DEFAULT_MODEL, HarnessError, _default_system_prompt, call_model

LOGGER = logging.getLogger("j_ui")
MAX_BODY_BYTES = 2_000_000
MAX_FILE_BYTES = 200_000

PAGE = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#101114">
<title>J · Local workspace</title>
<style>
:root{color-scheme:dark;--bg:#101114;--panel:#17181c;--panel2:#1d1f24;--line:#2b2d33;--text:#eeeae2;--muted:#9a9ba3;--accent:#d4a574;--green:#8bc49b;--red:#e58a83;--radius:14px;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);height:100vh;overflow:hidden}button,input,textarea{font:inherit;color:inherit}button{cursor:pointer}.shell{height:100%;display:grid;grid-template-columns:260px minmax(0,1fr) 270px}.sidebar{background:#131417;border-right:1px solid var(--line);display:flex;flex-direction:column;padding:17px 13px;min-width:0}.brand{display:flex;align-items:center;gap:11px;padding:4px 7px 19px}.mark{width:32px;height:32px;border:1px solid #735b42;border-radius:10px;display:grid;place-items:center;color:var(--accent);font-family:Georgia,serif;font-size:19px}.brand-name{font-weight:650;letter-spacing:.02em}.brand-sub{font-size:11px;color:var(--muted);margin-top:3px}.new-chat{display:flex;align-items:center;gap:9px;padding:10px 12px;border:1px solid var(--line);border-radius:10px;background:var(--panel);text-align:left}.new-chat:hover,.quiet:hover,.thread:hover{background:#222329}.section-label{font-size:10px;text-transform:uppercase;letter-spacing:.14em;color:var(--muted);padding:21px 8px 8px}.thread-list{overflow:auto;flex:1}.thread{width:100%;display:block;text-align:left;background:transparent;border:0;border-radius:8px;color:#c9c8c3;padding:9px 10px;font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.thread.active{background:#24252a;color:var(--text)}.sidebar-bottom{border-top:1px solid var(--line);padding-top:12px}.quiet{display:flex;gap:9px;align-items:center;width:100%;background:transparent;border:0;border-radius:8px;padding:9px 10px;text-align:left;color:#c7c6c1;font-size:12px}.main{display:flex;flex-direction:column;min-width:0;position:relative}.topbar{height:58px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid var(--line);padding:0 23px}.workspace-label{font-size:12px;color:var(--muted)}.model-select{background:var(--panel);border:1px solid var(--line);padding:7px 10px;border-radius:9px;font-size:12px;max-width:230px}.transcript{flex:1;overflow:auto;padding:45px max(24px,calc((100% - 760px)/2)) 25px}.welcome{max-width:700px;margin:12vh auto 0}.eyebrow{font-size:11px;text-transform:uppercase;letter-spacing:.14em;color:var(--accent)}h1{font-family:Georgia,"Times New Roman",serif;font-weight:400;font-size:clamp(34px,5vw,52px);line-height:1.08;letter-spacing:-.03em;margin:19px 0 12px}.welcome p{color:var(--muted);font-size:15px;line-height:1.7;max-width:580px}.suggestions{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:30px}.suggestion{background:var(--panel);border:1px solid var(--line);border-radius:11px;padding:14px;text-align:left;color:#dedbd4;font-size:12px;line-height:1.5}.suggestion:hover{border-color:#705c48}.suggestion strong{display:block;color:var(--accent);font-size:11px;margin-bottom:5px;font-weight:600}.message{max-width:760px;margin:0 auto 27px;line-height:1.72;font-size:14px;white-space:pre-wrap;overflow-wrap:anywhere}.message.user{padding:14px 16px;background:var(--panel2);border:1px solid var(--line);border-radius:13px}.message-role{font-size:10px;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);margin-bottom:7px}.message.assistant .message-role{color:var(--accent)}.message-text{white-space:pre-wrap}.composer-wrap{padding:10px 24px 23px}.composer{max-width:780px;margin:0 auto;background:var(--panel);border:1px solid #393a40;border-radius:15px;padding:12px 13px 10px;box-shadow:0 12px 40px #0003}.composer:focus-within{border-color:#75614b}.composer textarea{width:100%;resize:none;border:0;outline:0;background:transparent;min-height:53px;max-height:210px;font-size:14px;line-height:1.5}.composer textarea::placeholder{color:#777981}.composer-footer{display:flex;align-items:center;justify-content:space-between}.composer-note{font-size:10px;color:var(--muted)}.send{border:0;background:var(--accent);color:#17130f;font-weight:650;border-radius:8px;padding:8px 13px;font-size:12px}.send:disabled{opacity:.5;cursor:wait}.right{border-left:1px solid var(--line);background:#131417;padding:20px 16px;overflow:auto}.right-title{font-size:11px;text-transform:uppercase;letter-spacing:.13em;color:var(--muted);margin:2px 0 14px}.status-card,.context-card{background:var(--panel);border:1px solid var(--line);border-radius:11px;padding:13px;margin-bottom:12px}.status-row{display:flex;align-items:center;justify-content:space-between;font-size:12px}.status-dot{width:7px;height:7px;background:var(--green);border-radius:50%;display:inline-block;margin-right:7px}.status-dot.off{background:var(--red)}.status-detail{font-size:11px;line-height:1.6;color:var(--muted);margin-top:9px;overflow-wrap:anywhere}.context-actions{display:flex;gap:7px;margin-top:10px}.small-btn{background:var(--panel2);border:1px solid var(--line);border-radius:8px;padding:7px 9px;font-size:11px}.file-input{font-size:11px;max-width:100%;margin-top:7px}.file-chip{display:flex;justify-content:space-between;align-items:center;margin-top:8px;background:#232329;border-radius:7px;padding:7px 8px;font-size:11px;gap:6px}.remove-file{border:0;background:transparent;color:var(--muted)}.notice{position:absolute;bottom:4px;left:0;right:0;text-align:center;color:#797b83;font-size:10px;pointer-events:none}.mobile-toggle{display:none}.empty-hidden{display:none!important}.error{color:var(--red);font-size:12px;margin:8px auto;max-width:760px}.typing{color:var(--muted);font-style:italic}.workspace-path{width:100%;background:#101114;border:1px solid var(--line);border-radius:7px;padding:8px;font-size:11px;margin-top:8px}.icon{font-size:16px;line-height:1;color:var(--accent)}@media(max-width:980px){.shell{grid-template-columns:220px minmax(0,1fr)}.right{display:none}}@media(max-width:650px){body{overflow:auto}.shell{grid-template-columns:1fr;height:100dvh}.sidebar{display:none}.right{display:none}.topbar{padding:0 14px}.transcript{padding:27px 15px 20px}.composer-wrap{padding:8px 12px 14px}.welcome{margin-top:10vh}.suggestions{grid-template-columns:1fr}.model-select{max-width:160px}}
</style>
</head>
<body>
<div class="shell">
<aside class="sidebar">
  <div class="brand"><div class="mark">J</div><div><div class="brand-name">J workspace</div><div class="brand-sub">Private. Local. Yours.</div></div></div>
  <button class="new-chat" id="newChat" data-testid="new-chat-btn"><span class="icon">＋</span> New conversation</button>
  <div class="section-label">Recent</div><div class="thread-list" id="threadList" data-testid="conversation-list"></div>
  <div class="sidebar-bottom"><button class="quiet" id="openDocs" data-testid="open-docs-btn">⌘ &nbsp; Harness guide</button><button class="quiet" id="clearAll" data-testid="clear-history-btn">◌ &nbsp; Clear local history</button></div>
</aside>
<main class="main">
  <header class="topbar"><div class="workspace-label">LOCAL SESSION <span id="sessionLabel">· new conversation</span></div><select class="model-select" id="modelSelect" data-testid="model-select" aria-label="Model"><option value="qwen2.5:7b">qwen2.5:7b</option></select></header>
  <section class="transcript" id="transcript" data-testid="chat-transcript" aria-live="polite"></section>
  <div class="composer-wrap"><form class="composer" id="chatForm"><textarea id="messageInput" data-testid="chat-input" placeholder="Message J…" rows="2" aria-label="Message J"></textarea><div class="composer-footer"><span class="composer-note">Enter to send · Shift + Enter for a new line</span><button class="send" id="sendButton" data-testid="send-message-btn" type="submit">Send ↗</button></div></form></div>
  <div class="notice">Runs on your machine · Conversation history stays in this browser</div>
</main>
<aside class="right">
  <div class="right-title">Local runtime</div>
  <div class="status-card"><div class="status-row"><span><i class="status-dot off" id="statusDot"></i><span id="statusText">Checking model…</span></span><button class="small-btn" id="refreshStatus" data-testid="refresh-status-btn">Refresh</button></div><div class="status-detail" id="statusDetail">Connecting to the configured local model server.</div></div>
  <div class="right-title" style="margin-top:22px">Workspace context</div>
  <div class="context-card"><div style="font-size:12px">Attach files from a local workspace</div><div class="status-detail">Selected file content is sent only to your configured model endpoint.</div><input class="workspace-path" id="workspacePath" data-testid="workspace-path-input" aria-label="Workspace path" placeholder="Workspace path (default: current folder)"><div class="context-actions"><button class="small-btn" id="loadFiles" data-testid="load-files-btn">Browse files</button><input class="file-input" id="filePicker" data-testid="file-picker-input" type="file" multiple aria-label="Attach files"></div><div id="fileList"></div><div id="selectedFiles"></div></div>
  <div class="right-title" style="margin-top:22px">Session privacy</div><div class="status-detail">No hosted backend. No sign-in. Conversation history is stored in this browser's local storage. The model endpoint must be loopback-only.</div>
</aside>
</div>
<script>
const $ = (id) => document.getElementById(id);
const HISTORY_KEY = "j.local.ui.conversations.v1";
const MODEL_KEY = "j.local.ui.model.v1";
let sessions = loadSessions();
let activeId = sessions[0]?.id || createSession().id;
let attachments = [];
let busy = false;
function loadSessions(){try{const value=JSON.parse(localStorage.getItem(HISTORY_KEY)||"[]");return Array.isArray(value)?value:[]}catch{return []}}
function saveSessions(){localStorage.setItem(HISTORY_KEY,JSON.stringify(sessions.slice(0,40)))}
function createSession(){const session={id:crypto.randomUUID(),title:"New conversation",messages:[],updatedAt:Date.now()};sessions.unshift(session);saveSessions();return session}
function activeSession(){return sessions.find((session)=>session.id===activeId)}
function escapeHtml(text){return String(text).replace(/[&<>"']/g,(char)=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char]))}
function renderSessions(){const list=$("threadList");list.replaceChildren();for(const session of sessions){const button=document.createElement("button");button.className="thread"+(session.id===activeId?" active":"");button.dataset.testid="conversation-item";button.textContent=session.title;button.title=session.title;button.onclick=()=>{activeId=session.id;render()};list.append(button)}}
function welcomeMarkup(){return `<div class="welcome"><div class="eyebrow">J · Local intelligence</div><h1>A clear mind for<br>the work ahead.</h1><p>Your private AI workspace, running on your own machine. Ask a question, explore an idea, or bring local files into the conversation.</p><div class="suggestions"><button class="suggestion" data-testid="suggestion-understand"><strong>UNDERSTAND</strong>Walk me through this codebase and identify its main moving parts.</button><button class="suggestion" data-testid="suggestion-debug"><strong>DEBUG</strong>Help me reason through a bug. I’ll share the error and relevant code.</button><button class="suggestion" data-testid="suggestion-plan"><strong>PLAN</strong>Turn a rough feature idea into a practical implementation plan.</button><button class="suggestion" data-testid="suggestion-review"><strong>REVIEW</strong>Review the attached context for correctness and edge cases.</button></div></div>`}
function render(){renderSessions();const session=activeSession();$("sessionLabel").textContent="· "+session.title;const transcript=$("transcript");transcript.replaceChildren();if(!session.messages.length){transcript.innerHTML=welcomeMarkup();transcript.querySelectorAll(".suggestion").forEach((button)=>button.addEventListener("click",()=>{const prompts={"suggestion-understand":"Walk me through this codebase and identify its main moving parts.","suggestion-debug":"Help me reason through a bug. I’ll share the error and relevant code.","suggestion-plan":"Turn a rough feature idea into a practical implementation plan.","suggestion-review":"Review the attached context for correctness and edge cases."};$("messageInput").value=prompts[button.dataset.testid];$("messageInput").focus()}));return}for(const message of session.messages){const article=document.createElement("article");article.className="message "+message.role;article.dataset.testid=message.role+"-message";article.innerHTML=`<div class="message-role">${message.role==="user"?"You":"J"}</div><div class="message-text">${escapeHtml(message.content)}</div>`;transcript.append(article)}transcript.scrollTop=transcript.scrollHeight}
function updateAttachments(){const container=$("selectedFiles");container.replaceChildren();attachments.forEach((file,index)=>{const chip=document.createElement("div");chip.className="file-chip";chip.dataset.testid="attached-file";const name=document.createElement("span");name.textContent=file.name;const remove=document.createElement("button");remove.className="remove-file";remove.type="button";remove.dataset.testid="remove-attachment-btn";remove.textContent="Remove";remove.onclick=()=>{attachments.splice(index,1);updateAttachments()};chip.append(name,remove);container.append(chip)})}
function setStatus(ready,detail){$("statusDot").classList.toggle("off",!ready);$("statusText").textContent=ready?"Model connected":"Model unavailable";$("statusDetail").textContent=detail}
async function refreshStatus(){setStatus(false,"Checking local model endpoint…");try{const response=await fetch("/api/models");const body=await response.json();if(!response.ok)throw new Error(body.error||"Model endpoint unavailable");setStatus(true,body.endpoint);const modelSelect=$("modelSelect");const selected=localStorage.getItem(MODEL_KEY)||body.default_model;const models=body.models||[];if(models.length){modelSelect.replaceChildren(...models.map((model)=>{const option=document.createElement("option");option.value=model;option.textContent=model;return option}));if(!models.includes(selected)){const option=document.createElement("option");option.value=selected;option.textContent=selected;modelSelect.prepend(option)}modelSelect.value=selected}else{modelSelect.value=selected}}catch(error){setStatus(false,error.message)}}
async function sendMessage(text){if(busy||!text.trim())return;busy=true;const session=activeSession();let message=text.trim();if(attachments.length){const fileBlock=attachments.map((file)=>`\n\n[ATTACHED FILE: ${file.name}]\n${file.content}`).join("");message+=fileBlock}session.messages.push({role:"user",content:text.trim()});if(session.messages.length===1){session.title=text.trim().slice(0,42)+(text.trim().length>42?"…":"")}session.updatedAt=Date.now();saveSessions();render();const typing=document.createElement("div");typing.className="message assistant typing";typing.dataset.testid="assistant-thinking";typing.textContent="J is thinking…";$("transcript").append(typing);$("sendButton").disabled=true;try{const response=await fetch("/api/chat",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({messages:session.messages,model:$("modelSelect").value,attachments})});const body=await response.json();if(!response.ok)throw new Error(body.error||"Request failed");session.messages.push({role:"assistant",content:body.reply});session.updatedAt=Date.now();saveSessions();attachments=[];updateAttachments()}catch(error){session.messages.push({role:"assistant",content:"Connection error: "+error.message});saveSessions()}finally{busy=false;$("sendButton").disabled=false;render();$("messageInput").focus()}}
$("newChat").onclick=()=>{activeId=createSession().id;render();$("messageInput").focus()};$("clearAll").onclick=()=>{if(confirm("Clear all conversations stored in this browser?")){sessions=[];activeId=createSession().id;render()}};$("openDocs").onclick=()=>window.open("/HEADLESS_CLI.md","_blank","noopener");$("refreshStatus").onclick=refreshStatus;$("modelSelect").onchange=()=>localStorage.setItem(MODEL_KEY,$("modelSelect").value);$("chatForm").addEventListener("submit",(event)=>{event.preventDefault();const input=$("messageInput");const value=input.value;input.value="";input.style.height="auto";sendMessage(value)});$("messageInput").addEventListener("keydown",(event)=>{if(event.key==="Enter"&&!event.shiftKey){event.preventDefault();$("chatForm").requestSubmit()}});$("messageInput").addEventListener("input",(event)=>{event.target.style.height="auto";event.target.style.height=Math.min(event.target.scrollHeight,210)+"px"});$("filePicker").addEventListener("change",async(event)=>{for(const file of event.target.files){if(file.size>200000){setStatus(false,`File too large to attach: ${file.name}`);continue}attachments.push({name:file.name,content:await file.text()})}updateAttachments();event.target.value=""});
$("loadFiles").onclick=async()=>{const path=$("workspacePath").value.trim();const url="/api/files"+(path?"?path="+encodeURIComponent(path):"");try{const response=await fetch(url);const body=await response.json();if(!response.ok)throw new Error(body.error||"Unable to list files");const box=$("fileList");box.replaceChildren();for(const file of body.files){const button=document.createElement("button");button.className="small-btn";button.style.display="block";button.style.width="100%";button.style.textAlign="left";button.style.marginTop="6px";button.textContent=file.path+(file.is_dir?"/":"");button.dataset.testid="workspace-file-item";button.onclick=async()=>{if(file.is_dir){$("workspacePath").value=file.path;$("loadFiles").click();return}const read=await fetch("/api/file?path="+encodeURIComponent(file.path));const content=await read.json();if(!read.ok){setStatus(false,content.error);return}if(content.content.length>200000){setStatus(false,"File is too large to attach");return}attachments.push({name:file.path,content:content.content});updateAttachments()};box.append(button)}}catch(error){setStatus(false,error.message)}};
render();refreshStatus();
</script>
</body>
</html>'''


def _loopback_endpoint(endpoint: str) -> str:
    parsed = urlparse(endpoint)
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"} or host not in {"localhost", "127.0.0.1", "::1"}:
        raise HarnessError("the UI only permits a loopback model endpoint")
    return endpoint


def _models_url(endpoint: str) -> str:
    parsed = urlparse(_loopback_endpoint(endpoint))
    path = parsed.path
    if path.endswith("/chat/completions"):
        path = path[: -len("/chat/completions")] + "/models"
    else:
        path = path.rstrip("/") + "/models"
    return urlunparse((parsed.scheme, parsed.netloc, path, "", "", ""))


def _workspace_path(root: Path, requested: str | None) -> Path:
    candidate = (root / requested).resolve() if requested else root
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise HarnessError("workspace path escapes the configured workspace root") from exc
    return candidate


def make_handler(
    endpoint: str,
    model: str,
    api_key: str,
    system_prompt: str,
    workspace: Path,
    timeout: int,
    call_model_fn: Callable[..., str] | None = None,
) -> type[BaseHTTPRequestHandler]:
    endpoint = _loopback_endpoint(endpoint)
    model_caller = call_model_fn or call_model
    root = workspace.resolve()

    class Handler(BaseHTTPRequestHandler):
        server_version = "JLocalUI/1.0"

        def log_message(self, format_string: str, *args: Any) -> None:
            LOGGER.info("%s - %s", self.client_address[0], format_string % args)

        def _send(self, status: int, payload: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(payload)

        def _json(self, status: int, payload: dict[str, Any]) -> None:
            self._send(status, json.dumps(payload).encode("utf-8"), "application/json; charset=utf-8")

        def _body(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 1 or length > MAX_BODY_BYTES:
                raise HarnessError("request body is empty or exceeds the size limit")
            try:
                value = json.loads(self.rfile.read(length))
            except json.JSONDecodeError as exc:
                raise HarnessError("request body must be valid JSON") from exc
            if not isinstance(value, dict):
                raise HarnessError("request body must be a JSON object")
            return value

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/":
                self._send(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")
                return
            if parsed.path == "/HEADLESS_CLI.md":
                doc = _default_system_prompt().parents[0] / "docs" / "HEADLESS_CLI.md"
                try:
                    content = doc.read_bytes()
                except OSError:
                    self._json(404, {"error": "Harness documentation not found"})
                    return
                self._send(200, content, "text/markdown; charset=utf-8")
                return
            if parsed.path == "/api/models":
                self._get_models()
                return
            if parsed.path == "/api/files":
                self._get_files(parse_qs(parsed.query).get("path", [""])[0])
                return
            if parsed.path == "/api/file":
                self._get_file(parse_qs(parsed.query).get("path", [""])[0])
                return
            self._json(404, {"error": "Not found"})

        def _get_models(self) -> None:
            request = Request(_models_url(endpoint), headers={"Authorization": f"Bearer {api_key}"} if api_key else {})
            try:
                with urlopen(request, timeout=timeout) as response:
                    body = json.loads(response.read().decode("utf-8"))
            except (OSError, TimeoutError, json.JSONDecodeError) as exc:
                self._json(502, {"error": f"Local model endpoint unavailable: {exc}"})
                return
            items = body.get("data", []) if isinstance(body, dict) else []
            names = [item.get("id") for item in items if isinstance(item, dict) and isinstance(item.get("id"), str)]
            self._json(200, {"endpoint": endpoint, "default_model": model, "models": names})

        def _get_files(self, requested: str) -> None:
            try:
                directory = _workspace_path(root, requested or None)
                if not directory.is_dir():
                    raise HarnessError("requested workspace path is not a directory")
                files = []
                for item in sorted(directory.iterdir(), key=lambda entry: (not entry.is_dir(), entry.name.lower())):
                    resolved = item.resolve()
                    try:
                        relative = resolved.relative_to(root)
                    except ValueError:
                        continue
                    files.append({"path": str(relative), "is_dir": item.is_dir()})
                self._json(200, {"files": files})
            except (OSError, HarnessError) as exc:
                self._json(400, {"error": str(exc)})

        def _get_file(self, requested: str) -> None:
            try:
                if not requested:
                    raise HarnessError("file path is required")
                target = _workspace_path(root, requested)
                if not target.is_file():
                    raise HarnessError("requested path is not a file")
                if target.stat().st_size > MAX_FILE_BYTES:
                    raise HarnessError("file exceeds the 200 KB context limit")
                content = target.read_text(encoding="utf-8")
                self._json(200, {"path": str(target.relative_to(root)), "content": content})
            except (OSError, UnicodeDecodeError, HarnessError) as exc:
                self._json(400, {"error": str(exc)})

        def do_POST(self) -> None:
            if urlparse(self.path).path != "/api/chat":
                self._json(404, {"error": "Not found"})
                return
            try:
                payload = self._body()
                messages = payload.get("messages")
                if not isinstance(messages, list) or not messages:
                    raise HarnessError("messages must be a non-empty array")
                safe_messages = []
                for message in messages:
                    if not isinstance(message, dict) or message.get("role") not in {"user", "assistant"}:
                        raise HarnessError("messages may contain only user and assistant turns")
                    content = message.get("content")
                    if not isinstance(content, str):
                        raise HarnessError("message content must be text")
                    safe_messages.append({"role": message["role"], "content": content})
                selected_model = payload.get("model", model)
                if not isinstance(selected_model, str) or not selected_model.strip():
                    raise HarnessError("model must be a non-empty string")
                prompt_messages = []
                if system_prompt:
                    prompt_messages.append({"role": "system", "content": system_prompt})
                prompt_messages.extend(safe_messages)
                reply = model_caller(endpoint, selected_model, api_key, prompt_messages, timeout)
                self._json(200, {"reply": reply, "model": selected_model})
            except HarnessError as exc:
                self._json(400, {"error": str(exc)})
            except Exception as exc:
                LOGGER.exception("Local chat request failed")
                self._json(502, {"error": f"Local model request failed: {type(exc).__name__}: {exc}"})

    return Handler


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Open J's local browser workspace.")
    parser.add_argument("--host", default="127.0.0.1", help="interface to bind; defaults to loopback only")
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
        parser.error("the UI server must bind to loopback (127.0.0.1, localhost, or ::1)")
    try:
        endpoint = _loopback_endpoint(args.endpoint)
        prompt = args.system_prompt.read_text(encoding="utf-8") if args.system_prompt else ""
        handler = make_handler(endpoint, args.model, args.api_key, prompt, args.workspace, args.timeout)
    except (OSError, HarnessError) as exc:
        parser.error(str(exc))
    server = ThreadingHTTPServer((args.host, args.port), handler)
    server.daemon_threads = True
    LOGGER.info("J local UI ready at http://%s:%s", args.host, args.port)
    LOGGER.info("Model endpoint: %s (%s)", endpoint, args.model)
    LOGGER.info("Workspace root: %s", args.workspace.resolve())
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        LOGGER.info("Shutting down local UI")
    finally:
        server.shutdown()
        server.server_close()
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    raise SystemExit(main())
