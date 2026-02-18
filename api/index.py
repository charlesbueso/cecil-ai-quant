"""Cecil AI – FastAPI backend for Vercel serverless deployment.

This serves as the API layer between the Next.js frontend and the
Cecil multi-agent financial research system.
Includes Supabase JWT auth and conversation persistence.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import tempfile
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Ensure src/ is on the Python path so `from cecil...` imports work
# in both local dev and Vercel serverless.
_src_dir = str(Path(__file__).resolve().parent.parent / "src")
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

load_dotenv()

# -- App setup --------------------------------------------------------

app = FastAPI(
    title="Cecil AI API",
    description="Multi-agent financial research system API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://*.vercel.app",
        os.getenv("FRONTEND_URL", "http://localhost:3000"),
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger = logging.getLogger(__name__)

# -- Auth -------------------------------------------------------------

security = HTTPBearer(auto_error=False)

_SUPABASE_URL = os.getenv("SUPABASE_URL", os.getenv("NEXT_PUBLIC_SUPABASE_URL", ""))
_SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
_SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")


def _get_supabase_client():
    """Get a Supabase client with service role key (bypasses RLS)."""
    from supabase import create_client
    return create_client(_SUPABASE_URL, _SUPABASE_SERVICE_ROLE_KEY)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict[str, Any]:
    """Verify the Supabase JWT and return user info.

    Uses the Supabase Auth API to validate the token, which handles
    both HS256 (legacy) and RS256 (newer projects) automatically.
    Returns a dict with at least 'sub' (user id) and 'email'.
    """
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = credentials.credentials

    try:
        sb = _get_supabase_client()
        user_response = sb.auth.get_user(token)
        user = user_response.user
        if not user:
            raise ValueError("No user returned")
        return {
            "sub": user.id,
            "email": user.email,
            "user_metadata": user.user_metadata,
        }
    except Exception as e:
        logger.warning(f"JWT verification failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def _get_user_id(user: dict[str, Any]) -> str:
    """Extract user ID from JWT payload."""
    return user.get("sub", "")


# Optional auth – returns None if no token provided (for health/examples)
async def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict[str, Any] | None:
    """Try to verify JWT but don't fail if missing."""
    if not credentials:
        return None
    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None

# -- In-memory task store (use Redis/DB in production) ----------------

_tasks: dict[str, dict[str, Any]] = {}
_uploaded_files: dict[str, str] = {}  # upload_id -> temp file path


# -- Request / Response models ----------------------------------------

class TaskRequest(BaseModel):
    """Request body for submitting a new analysis task."""

    task: str = Field(..., min_length=1, max_length=5000, description="The analysis task to perform")
    max_iterations: int | None = Field(None, ge=1, le=50, description="Max agent iterations")
    generate_html: bool = Field(True, description="Generate HTML report")
    generate_pdf: bool = Field(False, description="Generate PDF report")
    file_ids: list[str] = Field(default_factory=list, description="IDs of previously uploaded files")
    stream: bool = Field(False, description="Enable streaming response")
    conversation_history: list[dict[str, str]] = Field(
        default_factory=list,
        description="Prior conversation messages [{role, content}] for context",
    )


class TaskResponse(BaseModel):
    """Response after submitting a task."""

    task_id: str
    status: str
    message: str


class TaskStatusResponse(BaseModel):
    """Status of a running task."""

    task_id: str
    status: str  # pending, in_progress, completed, failed
    progress: list[dict[str, Any]] = []
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: str | None = None


class ExampleTask(BaseModel):
    """An example task preset."""

    name: str
    description: str
    task: str


class ReportInfo(BaseModel):
    """Metadata about a generated report."""

    filename: str
    task: str
    created_at: str
    type: str  # html or pdf


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str
    timestamp: str
    providers: dict[str, bool]
    data_providers: dict[str, bool] = {}


# -- Helper functions -------------------------------------------------

def _extract_final_output(state: dict) -> str:
    """Extract the final synthesis from the agent state."""
    # Try sub_task first (PM's final synthesis)
    sub_task = state.get("sub_task", "")
    if sub_task and len(sub_task) > 100:
        # Make sure it's not raw JSON — clean it if needed
        cleaned = _extract_synthesis_from_json(sub_task)
        return cleaned

    # Fall back to last AI message
    messages = state.get("messages", [])
    for msg in reversed(messages):
        if hasattr(msg, "content") and msg.content:
            content = msg.content if isinstance(msg.content, str) else str(msg.content)
            if len(content) > 50:
                # If the content looks like PM routing JSON, extract the sub_task
                content = _extract_synthesis_from_json(content)
                return content

    # Last resort — check agent_outputs for the PM's final output
    agent_outputs = state.get("agent_outputs", {})
    pm_output = agent_outputs.get("project_manager", "")
    if pm_output:
        return _extract_synthesis_from_json(pm_output)

    return "Analysis completed but no summary was generated."


def _extract_synthesis_from_json(text: str) -> str:
    """If text is PM routing JSON, extract the sub_task as the synthesis."""
    import re as _re

    stripped = text.strip()
    if not (stripped.startswith("{") or stripped.startswith("```")):
        return text

    # Step 1: Try to parse as proper JSON (code-fenced or raw)
    try:
        m = _re.search(r"```(?:json)?\s*(\{.*?\})\s*```", stripped, _re.DOTALL)
        raw = m.group(1) if m else stripped
        data = json.loads(raw)
        sub_task = data.get("sub_task", "")
        if sub_task and len(sub_task) > 50:
            return sub_task
        reasoning = data.get("reasoning", "")
        if reasoning:
            return f"{reasoning}\n\n{sub_task}" if sub_task else reasoning
    except (json.JSONDecodeError, TypeError):
        pass

    # Step 2: Fix common JSON issues (unescaped newlines) and retry
    try:
        # Replace literal newlines inside JSON string values with \n
        fixed = _re.sub(r'(?<=")([^"]*?)\n([^"]*?)(?=")', 
                        lambda m: m.group(0).replace('\n', '\\n'), stripped)
        # Try multiple passes for multi-line values
        for _ in range(20):
            prev = fixed
            fixed = _re.sub(r'(?<=")([^"]*?)\n([^"]*?)(?=")',
                           lambda m: m.group(0).replace('\n', '\\n'), fixed)
            if fixed == prev:
                break
        m2 = _re.search(r"```(?:json)?\s*(\{.*?\})\s*```", fixed, _re.DOTALL)
        raw2 = m2.group(1) if m2 else fixed
        data = json.loads(raw2)
        sub_task = data.get("sub_task", "")
        if sub_task and len(sub_task) > 50:
            return sub_task
    except (json.JSONDecodeError, TypeError):
        pass

    # Step 3: Regex fallback — extract sub_task value directly
    m3 = _re.search(r'"sub_task"\s*:\s*"(.*)', stripped, _re.DOTALL)
    if m3:
        val = m3.group(1)
        val = val.rstrip()
        # Remove trailing JSON closure
        if val.endswith('"}'):
            val = val[:-2]
        elif val.endswith('"'):
            val = val[:-1]
        val = _re.sub(r'"\s*,?\s*\}\s*$', '', val)
        if len(val) > 50:
            return val

    return text


def _humanize_pm_summary(summary: str) -> str:
    """Convert PM JSON routing output into human-readable text."""
    if not summary:
        return summary
    text = summary.strip()
    if not (text.startswith("{") or text.startswith("```")):
        return summary  # not JSON
    try:
        # Strip markdown code fences if present
        import re as _re
        m = _re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, _re.DOTALL)
        raw = m.group(1) if m else text
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return summary
    parts = []
    reasoning = data.get("reasoning", "")
    sub_task = data.get("sub_task", "")
    next_agent = data.get("next_agent", "")
    if next_agent and next_agent != "__end__":
        parts.append(f"**Routing to {next_agent.replace('_', ' ').title()}**")
    if reasoning:
        parts.append(reasoning)
    if sub_task:
        parts.append(f"*Task: {sub_task}*")
    return "\n\n".join(parts) if parts else summary


def _extract_agent_steps(state: dict) -> list[dict[str, Any]]:
    """Extract structured agent step info from results."""
    results = state.get("results", [])
    steps = []
    for r in results:
        summary = r.get("summary", "")
        if r.get("agent") == "project_manager":
            summary = _humanize_pm_summary(summary)
        steps.append({
            "agent": r.get("agent", "unknown"),
            "summary": summary,
            "tool_calls": r.get("tool_calls_made", 0),
            "status": r.get("status", "completed"),
        })
    return steps


def _check_provider_keys() -> dict[str, bool]:
    """Check which LLM provider API keys are configured."""
    return {
        "groq": bool(os.getenv("GROQ_API_KEY", "")),
        "together": bool(os.getenv("TOGETHER_API_KEY", "")),
        "fireworks": bool(os.getenv("FIREWORKS_API_KEY", "")),
        "openrouter": bool(os.getenv("OPENROUTER_API_KEY", "")),
    }


def _check_data_provider_keys() -> dict[str, bool]:
    """Check which data provider API keys are configured."""
    return {
        "fred": bool(os.getenv("FRED_API_KEY", "")),
        "fmp": bool(os.getenv("FMP_API_KEY", "")),
        "finnhub": bool(os.getenv("FINNHUB_API_KEY", "")),
        "alpha_vantage": bool(os.getenv("ALPHA_VANTAGE_API_KEY", "")),
        "news_api": bool(os.getenv("NEWS_API_KEY", "")),
    }


# -- Endpoints --------------------------------------------------------

@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        version="0.1.0",
        timestamp=datetime.now(timezone.utc).isoformat(),
        providers=_check_provider_keys(),
        data_providers=_check_data_provider_keys(),
    )


@app.get("/api/examples", response_model=list[ExampleTask])
async def get_examples():
    """Get available example/preset tasks."""
    from cecil.main import EXAMPLE_TASKS

    return [
        ExampleTask(name=name, description=task[:100] + "...", task=task)
        for name, task in EXAMPLE_TASKS.items()
    ]


@app.post("/api/task", response_model=TaskStatusResponse)
async def submit_task(request: TaskRequest, user: dict = Depends(get_current_user)):
    """Submit and execute an analysis task synchronously.

    For Vercel serverless, this runs the task inline and returns results.
    For long tasks, use the streaming endpoint instead.
    """
    task_id = str(uuid.uuid4())[:8]

    try:
        from cecil.main import run_task

        # Resolve uploaded file paths
        file_paths = []
        for fid in request.file_ids:
            if fid in _uploaded_files:
                file_paths.append(_uploaded_files[fid])

        result = run_task(
            request.task,
            max_iterations=request.max_iterations,
            stream=False,
            generate_pdf=request.generate_pdf,
            generate_html=request.generate_html,
            file_paths=file_paths if file_paths else None,
        )

        # Extract useful info from state
        final_output = _extract_final_output(result)
        agent_steps = _extract_agent_steps(result)

        _tasks[task_id] = {
            "status": "completed",
            "result": {
                "output": final_output,
                "agent_steps": agent_steps,
                "iterations": result.get("iteration", 0),
                "agent_outputs": result.get("agent_outputs", {}),
            },
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        return TaskStatusResponse(
            task_id=task_id,
            status="completed",
            progress=agent_steps,
            result=_tasks[task_id]["result"],
            created_at=_tasks[task_id]["created_at"],
        )

    except Exception as e:
        logger.error(f"Task execution failed: {e}", exc_info=True)
        error_detail = f"{type(e).__name__}: {str(e)}"
        _tasks[task_id] = {
            "status": "failed",
            "error": error_detail,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        return TaskStatusResponse(
            task_id=task_id,
            status="failed",
            error=error_detail,
            created_at=_tasks[task_id]["created_at"],
        )


@app.post("/api/task/stream")
async def submit_task_stream(request: TaskRequest, raw_request: Request, user: dict = Depends(get_current_user)):
    """Submit a task and stream results via Server-Sent Events."""

    async def event_generator():
        try:
            import time as _time

            from cecil.main import run_task, _setup_logging
            from cecil.graph.builder import compile_graph
            from cecil.state.schema import AgentState
            from cecil.utils.file_parser import parse_file, format_file_context, is_image_file
            from cecil.config import get_settings
            from langchain_core.messages import HumanMessage, AIMessage

            _setup_logging()
            settings = get_settings()

            # Global task timeout (seconds)
            _TASK_TIMEOUT = 300  # 5 minutes max
            _task_start = _time.monotonic()

            # Parse files if provided
            file_context = ""
            image_contents: list[dict[str, str]] = []
            if request.file_ids:
                file_contexts = []
                for fid in request.file_ids:
                    if fid in _uploaded_files:
                        file_path = _uploaded_files[fid]
                        if is_image_file(file_path):
                            file_info = parse_file(file_path)
                            image_contents.append({
                                "name": file_info["name"],
                                "type": file_info["type"],
                                "data_url": file_info["data_url"],
                            })
                        else:
                            file_info = parse_file(file_path)
                            file_contexts.append(format_file_context(file_info))
                file_context = "\n\n".join(file_contexts)

            # -- Image pre-processing: extract text descriptions via vision model --
            if image_contents:
                try:
                    from cecil.models.client import get_model_client
                    _vision_client = get_model_client()
                    _vision_llm = _vision_client.get_chat_model(
                        role="project_manager",
                        provider_name="groq",
                        model="meta-llama/llama-4-scout-17b-16e-instruct",
                        max_tokens=2048,
                    )
                    # Build multimodal message to extract image content
                    _img_content_blocks: list[dict] = [{
                        "type": "text",
                        "text": (
                            "You are a financial document and chart analyst. "
                            "Carefully examine the provided image(s). Extract ALL visible information: "
                            "text, numbers, labels, axis values, chart titles, data points, trends, "
                            "table data, percentages, dates, and any other relevant details. "
                            "Be thorough and precise — your extracted description will be used "
                            "by financial analysts who cannot see the image."
                        ),
                    }]
                    for img in image_contents:
                        if img.get("data_url"):
                            _img_content_blocks.append({
                                "type": "image_url",
                                "image_url": {"url": img["data_url"]},
                            })
                    _vision_msg = HumanMessage(content=_img_content_blocks)
                    _vision_response = _vision_llm.invoke([_vision_msg])
                    _extracted = _vision_response.content if isinstance(_vision_response.content, str) else str(_vision_response.content)

                    # Append extracted image content to file_context
                    _img_names = ", ".join(img.get("name", "image") for img in image_contents)
                    _img_section = (
                        f"\n\n--- UPLOADED IMAGE ANALYSIS ({_img_names}) ---\n"
                        f"{_extracted}\n"
                        f"--- END IMAGE ANALYSIS ---\n"
                    )
                    file_context = file_context + _img_section if file_context else _img_section.strip()
                    logging.info("Vision pre-processing extracted %d chars from %d image(s)", len(_extracted), len(image_contents))
                except Exception as _vision_exc:
                    logging.warning("Vision pre-processing failed: %s — images will be passed raw to agents", _vision_exc)

            app_graph = compile_graph()

            # Build message history from prior conversation
            history_messages = []
            for msg in request.conversation_history:
                role = msg.get("role", "")
                content = msg.get("content", "")
                if not content:
                    continue
                if role == "user":
                    history_messages.append(HumanMessage(content=content))
                elif role == "assistant":
                    history_messages.append(AIMessage(content=content))
                # skip system messages

            # Append the current task as the latest user message
            history_messages.append(HumanMessage(content=request.task))

            initial_state: AgentState = {
                "messages": history_messages,
                "task": request.task,
                "current_agent": "project_manager",
                "next_agent": "project_manager",
                "sub_task": "",
                "context": {},
                "results": [],
                "agent_outputs": {},
                "iteration": 0,
                "max_iterations": request.max_iterations or settings.max_agent_iterations,
                "status": "in_progress",
                "error": "",
                "file_context": file_context,
                "image_contents": image_contents,
            }

            yield f"data: {json.dumps({'type': 'start', 'message': 'Analysis started'})}\n\n"

            final_state = None
            # Accumulate results & agent_outputs across streaming deltas
            # (each step yields a delta, not the full state)
            all_results: list[dict] = []
            all_agent_outputs: dict[str, str] = {}
            _SENTINEL = object()
            _cancelled = False
            graph_iter = app_graph.stream(initial_state, {"recursion_limit": 50}).__iter__()

            while True:
                # Run next(graph_iter) in a thread so we can poll for disconnect
                step_future = asyncio.ensure_future(
                    asyncio.to_thread(next, graph_iter, _SENTINEL)
                )

                # Poll for disconnect every 500ms while waiting for the step
                while not step_future.done():
                    if await raw_request.is_disconnected():
                        logger.info("Client disconnected — aborting task")
                        step_future.cancel()
                        _cancelled = True
                        break
                    if _time.monotonic() - _task_start > _TASK_TIMEOUT:
                        step_future.cancel()
                        _cancelled = True
                        yield f"data: {json.dumps({'type': 'error', 'message': f'Task timed out after {_TASK_TIMEOUT}s'})}\n\n"
                        break
                    await asyncio.sleep(0.5)

                if _cancelled:
                    break

                try:
                    step = step_future.result()
                except (asyncio.CancelledError, Exception):
                    break

                if step is _SENTINEL:
                    break  # iterator exhausted

                node_name = list(step.keys())[0]
                state_snapshot = step[node_name]
                # Accumulate results (operator.add behaviour)
                all_results.extend(state_snapshot.get("results", []))
                # Accumulate agent_outputs (merge behaviour)
                for k, v in state_snapshot.get("agent_outputs", {}).items():
                    if k in all_agent_outputs:
                        all_agent_outputs[k] = all_agent_outputs[k] + "\n\n" + v
                    else:
                        all_agent_outputs[k] = v
                final_state = state_snapshot

                # Extract latest result for this step
                results = state_snapshot.get("results", [])
                latest = results[-1] if results else {}

                raw_summary = latest.get("summary", "")
                if node_name == "project_manager":
                    raw_summary = _humanize_pm_summary(raw_summary)
                raw_summary = raw_summary[:800]

                step_data = {
                    "type": "step",
                    "agent": node_name,
                    "summary": raw_summary,
                    "tool_calls": latest.get("tool_calls_made", 0),
                    "iteration": state_snapshot.get("iteration", 0),
                }
                yield f"data: {json.dumps(step_data)}\n\n"
                await asyncio.sleep(0)  # yield control

            if final_state:
                # Patch the final snapshot with fully accumulated data
                final_state["results"] = all_results
                final_state["agent_outputs"] = all_agent_outputs
                final_output = _extract_final_output(final_state)
                agent_steps = _extract_agent_steps(final_state)

                # Generate HTML report if requested
                report_html = None
                if request.generate_html:
                    try:
                        from cecil.utils.html_report import CecilHTMLReport
                        html_gen = CecilHTMLReport()
                        html_path = html_gen.generate_report(final_state, request.task)
                        with open(html_path, "r", encoding="utf-8") as f:
                            report_html = f.read()
                    except Exception:
                        pass

                done_data = {
                    "type": "done",
                    "output": final_output,
                    "agent_steps": agent_steps,
                    "iterations": final_state.get("iteration", 0),
                    "agent_outputs": final_state.get("agent_outputs", {}),
                    "report_html": report_html,
                }
                yield f"data: {json.dumps(done_data)}\n\n"
            else:
                yield f"data: {json.dumps({'type': 'error', 'message': 'No result produced'})}\n\n"

        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
            yield f"data: {json.dumps({'type': 'error', 'message': error_msg})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/task/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    """Get the status and result of a previously submitted task."""
    if task_id not in _tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    task_data = _tasks[task_id]
    return TaskStatusResponse(
        task_id=task_id,
        status=task_data["status"],
        result=task_data.get("result"),
        error=task_data.get("error"),
        created_at=task_data.get("created_at"),
    )


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    """Upload a file (CSV, PDF, TXT, images, etc.) for use as context in tasks."""
    allowed_extensions = {
        ".csv", ".txt", ".md", ".json", ".pdf",
        ".py", ".js", ".ts", ".yaml", ".yml", ".log",
        ".png", ".jpg", ".jpeg", ".gif", ".webp",
    }

    filename = file.filename or "upload"
    ext = Path(filename).suffix.lower()

    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Allowed: {', '.join(sorted(allowed_extensions))}",
        )

    # Save to temp file
    upload_id = str(uuid.uuid4())[:8]
    tmp_dir = Path(tempfile.gettempdir()) / "cecil_uploads"
    tmp_dir.mkdir(exist_ok=True)
    tmp_path = tmp_dir / f"{upload_id}_{filename}"

    content = await file.read()
    with open(tmp_path, "wb") as f:
        f.write(content)

    _uploaded_files[upload_id] = str(tmp_path)

    # Persist to Supabase Storage for long-term access
    storage_url = None
    user_id = _get_user_id(user)
    try:
        sb = _get_supabase_client()
        storage_path = f"{user_id}/{upload_id}_{filename}"
        # Determine content type
        import mimetypes
        content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        sb.storage.from_("chat-attachments").upload(
            path=storage_path,
            file=content,
            file_options={"content-type": content_type},
        )
        # Build public URL
        storage_url = f"{_SUPABASE_URL}/storage/v1/object/public/chat-attachments/{storage_path}"
        logger.info("File persisted to storage: %s", storage_path)
    except Exception as e:
        logger.warning("Failed to persist file to Supabase Storage: %s", e)

    return JSONResponse({
        "upload_id": upload_id,
        "filename": filename,
        "size": len(content),
        "url": storage_url,
        "type": ext.lstrip("."),
        "message": "File uploaded successfully",
    })


@app.delete("/api/upload/{upload_id}")
async def delete_upload(upload_id: str, user: dict = Depends(get_current_user)):
    """Delete an uploaded file from temp storage and Supabase Storage."""
    user_id = _get_user_id(user)

    # Remove from in-memory temp store
    tmp_path = _uploaded_files.pop(upload_id, None)
    if tmp_path:
        try:
            Path(tmp_path).unlink(missing_ok=True)
        except Exception:
            pass

    # Remove from Supabase Storage
    try:
        sb = _get_supabase_client()
        # List files in user's folder matching this upload_id prefix
        files = sb.storage.from_("chat-attachments").list(user_id)
        to_delete = [f["name"] for f in files if f["name"].startswith(upload_id)]
        if to_delete:
            sb.storage.from_("chat-attachments").remove(
                [f"{user_id}/{name}" for name in to_delete]
            )
            logger.info("Deleted %d file(s) from storage for upload %s", len(to_delete), upload_id)
    except Exception as e:
        logger.warning("Failed to delete from Supabase Storage: %s", e)

    return JSONResponse({"status": "deleted"})


@app.get("/api/reports")
async def list_reports():
    """List all generated reports."""
    reports_dir = Path("reports")
    if not reports_dir.exists():
        return []

    reports = []
    for f in sorted(reports_dir.iterdir(), reverse=True):
        if f.suffix in (".html", ".pdf"):
            # Parse task name from filename
            name = f.stem
            parts = name.replace("cecil_report_", "").rsplit("_", 2)
            task_name = parts[0].replace("_", " ") if parts else name

            reports.append(ReportInfo(
                filename=f.name,
                task=task_name,
                created_at=datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
                type=f.suffix[1:],
            ))

    return reports


@app.get("/api/reports/{filename}")
async def get_report(filename: str):
    """Get a specific report by filename."""
    reports_dir = Path("reports")
    filepath = reports_dir / filename

    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Report not found")

    if filepath.suffix == ".html":
        content = filepath.read_text(encoding="utf-8")
        return HTMLResponse(content=content)
    else:
        raise HTTPException(status_code=400, detail="Only HTML reports can be viewed")


@app.get("/api/agents")
async def get_agents():
    """Get information about available agents."""
    return [
        {
            "id": "project_manager",
            "name": "Project Manager",
            "description": "Orchestrates the analysis by coordinating specialist agents",
            "color": "#a855f7",
            "icon": "crown",
        },
        {
            "id": "quant_researcher",
            "name": "Quant Researcher",
            "description": "Quantitative analysis, stock data, factor computation, and market metrics",
            "color": "#06b6d4",
            "icon": "chart-bar",
        },
        {
            "id": "portfolio_analyst",
            "name": "Portfolio Analyst",
            "description": "Portfolio construction, risk metrics, diversification, and rebalancing",
            "color": "#22c55e",
            "icon": "briefcase",
        },
        {
            "id": "research_intelligence",
            "name": "Research Intelligence",
            "description": "Financial news, macro data, market sentiment, and economic indicators",
            "color": "#eab308",
            "icon": "newspaper",
        },
    ]


# -- Conversation endpoints -------------------------------------------


class ConversationCreate(BaseModel):
    title: str = Field("", max_length=200)


class MessageCreate(BaseModel):
    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str = Field(..., min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


@app.get("/api/conversations")
async def list_conversations(user: dict = Depends(get_current_user)):
    """List all conversations for the authenticated user."""
    user_id = _get_user_id(user)
    sb = _get_supabase_client()
    result = (
        sb.table("conversations")
        .select("*")
        .eq("user_id", user_id)
        .order("updated_at", desc=True)
        .limit(50)
        .execute()
    )
    return result.data


@app.post("/api/conversations")
async def create_convo(body: ConversationCreate, user: dict = Depends(get_current_user)):
    """Create a new conversation."""
    user_id = _get_user_id(user)
    sb = _get_supabase_client()
    result = (
        sb.table("conversations")
        .insert({"user_id": user_id, "title": body.title or "New Conversation"})
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to create conversation")
    return result.data[0]


@app.get("/api/conversations/{conversation_id}/messages")
async def list_messages(conversation_id: str, user: dict = Depends(get_current_user)):
    """Get all messages for a conversation."""
    user_id = _get_user_id(user)
    sb = _get_supabase_client()

    # Verify conversation belongs to user
    convo = (
        sb.table("conversations")
        .select("id")
        .eq("id", conversation_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not convo.data:
        raise HTTPException(status_code=404, detail="Conversation not found")

    result = (
        sb.table("messages")
        .select("*")
        .eq("conversation_id", conversation_id)
        .order("created_at", desc=False)
        .execute()
    )
    return result.data


@app.post("/api/conversations/{conversation_id}/messages")
async def add_message(
    conversation_id: str, body: MessageCreate, user: dict = Depends(get_current_user)
):
    """Add a message to a conversation."""
    user_id = _get_user_id(user)
    sb = _get_supabase_client()

    # Verify conversation belongs to user
    convo = (
        sb.table("conversations")
        .select("id")
        .eq("id", conversation_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not convo.data:
        raise HTTPException(status_code=404, detail="Conversation not found")

    result = (
        sb.table("messages")
        .insert({
            "conversation_id": conversation_id,
            "role": body.role,
            "content": body.content,
            "metadata": body.metadata,
        })
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to save message")

    # Update conversation's updated_at
    sb.table("conversations").update(
        {"updated_at": datetime.now(timezone.utc).isoformat()}
    ).eq("id", conversation_id).execute()

    return result.data[0]


@app.delete("/api/conversations/{conversation_id}")
async def delete_convo(conversation_id: str, user: dict = Depends(get_current_user)):
    """Delete a conversation and all its messages."""
    user_id = _get_user_id(user)
    sb = _get_supabase_client()

    # Verify conversation belongs to user
    convo = (
        sb.table("conversations")
        .select("id")
        .eq("id", conversation_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not convo.data:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Messages cascade-delete via FK
    sb.table("conversations").delete().eq("id", conversation_id).execute()
    return {"status": "deleted"}
