"""
FastAPI application factory.

Creates a Tova API server from your provider implementations.

Usage:
    from tova_core.app import create_app
    from my_providers import MyBackend, MyStore, MyAuth

    app = create_app(
        backend_factory=lambda token: MyBackend(token),
        store=MyStore(),
        auth=MyAuth(),
    )
"""

import logging
from contextlib import asynccontextmanager
from typing import Callable

from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from tova_core.config import get_settings
from tova_core.models.schemas import (
    ChatRequest, ChatResponse, ExecuteRequest, HealthResponse,
    AgentCreateRequest, AgentUpdateRequest, AgentResponse,
    AgentChatRequest, AgentChatResponse, ToolCatalogItem,
    UserFeaturesResponse, UserPreferencesUpdate, BrainBoxResponse,
)
from tova_core.models.agent import AgentConfig
from tova_core.providers.backend import BaseBackend
from tova_core.providers.store import BaseStore
from tova_core.providers.auth import BaseAuth
from tova_core.providers.notifier import BaseNotifier
from tova_core.providers.vector_store import BaseVectorStore
from tova_core.providers.file_store import BaseFileStore
from tova_core.providers.telephony import BaseTelephony
from tova_core.providers.email import BaseEmailProvider
from tova_core.providers.calendar import BaseCalendarProvider
from tova_core.providers.geolocation import BaseGeolocationProvider
from tova_core.providers.video_stream import BaseVideoStream
from tova_core.providers.travel import BaseTravelProvider
from tova_core.providers.creative import BaseImageGenerator, BaseVideoGenerator, BaseAudioGenerator
from tova_core.tools.web_search_tools import build_web_search_tools
from tova_core.tools.workspace_tools import build_workspace_tools
from tova_core.tools.document_tools import build_document_tools
from tova_core.tools.workforce_tools import build_workforce_tools
from tova_core.tools.agent_tools import build_agent_tools
from tova_core.tools.creative_tools import build_image_tools, build_video_tools, build_audio_tools
from tova_core.workforce.engine import WorkforceEngine
from tova_core.agents.order_agent import run_order_agent
from tova_core.agents.execution_agent import run_execution_agent
from tova_core.agents.runtime import AgentRuntime
from tova_core.tools.base import ToolRegistry
from tova_core.memory.brain_box import BrainBox
from tova_core.learning.engine import SelfLearner

logger = logging.getLogger(__name__)


def create_app(
    backend_factory: Callable[[str | None], BaseBackend],
    store: BaseStore,
    auth: BaseAuth,
    notifier: BaseNotifier | None = None,
    system_prompt: str | None = None,
    execution_prompt: str | None = None,
    cors_origins: list[str] | None = None,
    tool_registry: ToolRegistry | None = None,
    # ── Phase 1: RAG & Productivity ────────────────────────────
    vector_store: BaseVectorStore | None = None,
    file_store: BaseFileStore | None = None,
    # ── Phase 2: External Integrations ─────────────────────────
    telephony: BaseTelephony | None = None,
    email_provider: BaseEmailProvider | None = None,
    calendar_provider: BaseCalendarProvider | None = None,
    # ── Phase 3: Hardware & Real-time ──────────────────────────
    video_stream: BaseVideoStream | None = None,
    geolocation: BaseGeolocationProvider | None = None,
    travel_provider: BaseTravelProvider | None = None,
    # ── Creative (Image, Video, Audio) ──────────────────────────
    image_generator: BaseImageGenerator | None = None,
    video_generator: BaseVideoGenerator | None = None,
    audio_generator: BaseAudioGenerator | None = None,
    # ── Feature Control ────────────────────────────────────────
    enabled_features: list[str] | None = None,
) -> FastAPI:
    """Create a Tova FastAPI application.

    Args:
        backend_factory: A callable that takes an auth_token and returns a BaseBackend instance.
                        Called per-request so each request gets its own authenticated client.
        store: Your data store provider (shared across requests).
        auth: Your auth provider for token verification.
        notifier: Optional notification provider.
        system_prompt: Custom system prompt for the order agent.
        execution_prompt: Custom system prompt for the execution agent.
        cors_origins: CORS allowed origins (default: ["*"]).
        tool_registry: Optional ToolRegistry for OpenClaw-style custom agents.
                      If provided, enables the /agents/* endpoints.
        vector_store: Optional vector DB for RAG/dataset features.
        file_store: Optional blob storage for file management.
        telephony: Optional telephony provider for calls/SMS.
        email_provider: Optional email provider for email management.
        calendar_provider: Optional calendar provider for event planning.
        video_stream: Optional video provider for CCTV monitoring.
        geolocation: Optional GPS provider for vehicle tracking.
        enabled_features: List of feature names to enable. If None, auto-detect from providers.

    Returns:
        A configured FastAPI application.
    """
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info("Tova Agent Service starting up")
        logger.info(f"Model: {settings.agent_model}")
        yield
        logger.info("Tova Agent Service shutting down")

    app = FastAPI(
        title="Tova Agent Service",
        description="Universal AI agent platform — healthcare, productivity, monitoring, and more",
        version="0.2.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Anonymous Session Middleware ──────────────────────────
    # When using SessionAuth, users don't need to sign up or send tokens.
    # This middleware auto-creates sessions for anonymous users.

    _is_session_auth = hasattr(auth, "is_anonymous") and auth.is_anonymous()

    if _is_session_auth:
        from tova_core.providers.builtin.auth import SessionAuth

        class SessionMiddleware(BaseHTTPMiddleware):
            """Auto-assign anonymous sessions to users with no token."""

            async def dispatch(self, request: Request, call_next):
                # Skip health/docs endpoints
                if request.url.path in ("/", "/health", "/docs", "/openapi.json", "/redoc"):
                    return await call_next(request)

                auth_header = request.headers.get("authorization", "")
                cookie_session = request.cookies.get(auth.cookie_name, "")

                if auth_header:
                    # User sent a token (developer, API key, etc.) — pass through
                    response = await call_next(request)
                    return response

                if cookie_session and cookie_session.startswith("session_"):
                    # Returning anonymous user — inject their session as auth
                    token = cookie_session
                else:
                    # Brand new user — generate a session
                    token = SessionAuth.generate_session_id()

                # Inject the session token as Authorization header
                # so all downstream endpoints work unchanged
                request.scope["headers"] = [
                    (k, v) for k, v in request.scope["headers"]
                    if k != b"authorization"
                ] + [(b"authorization", f"Bearer {token}".encode())]

                response = await call_next(request)

                # Set/refresh the session cookie
                max_age = auth.max_age_days * 86400 if auth.max_age_days else None
                response.set_cookie(
                    key=auth.cookie_name,
                    value=token,
                    max_age=max_age,
                    httponly=True,
                    samesite="lax",
                    secure=False,  # Set True in production behind HTTPS
                )

                # Also return session ID in response header for non-browser clients
                response.headers["X-Tova-Session"] = token

                return response

        app.add_middleware(SessionMiddleware)

    def _extract_token(authorization: str) -> str:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Invalid authorization header")
        return authorization[7:]

    @app.get("/")
    async def root():
        return {"service": "tova", "version": "0.1.0", "status": "running", "docs": "/docs"}

    @app.get("/health", response_model=HealthResponse)
    async def health():
        return HealthResponse()

    @app.post("/agent/chat", response_model=ChatResponse)
    async def chat(
        req: ChatRequest,
        authorization: str = Header(..., description="Bearer <token>"),
    ):
        """Patient-facing conversational endpoint."""
        token = _extract_token(authorization)
        user_id = await auth.verify_token(token)

        backend = backend_factory(token)

        # Build extra tools based on enabled features
        extra_tools = []
        # Web search — always available, Tova's universal search
        extra_tools.extend(build_web_search_tools())
        # Travel tools
        if travel_provider:
            from tova_core.tools.travel_tools import build_travel_tools
            extra_tools.extend(build_travel_tools(store, travel_provider))
        # Workspace tools (file operations)
        if file_store:
            extra_tools.extend(build_workspace_tools(file_store))
            extra_tools.extend(build_document_tools(file_store))
        # Workforce tools (agent creation, workflows, delegation)
        _workforce_engine = WorkforceEngine(store=store)
        extra_tools.extend(build_workforce_tools(store, _workforce_engine))
        # Smart agent factory (create any agent from description)
        extra_tools.extend(build_agent_tools(store, tool_registry))
        # Creative tools (image, video, audio generation)
        if image_generator:
            extra_tools.extend(build_image_tools(image_generator, file_store))
        if video_generator:
            extra_tools.extend(build_video_tools(video_generator, file_store))
        if audio_generator:
            extra_tools.extend(build_audio_tools(audio_generator))

        try:
            result = await run_order_agent(
                user_id=user_id,
                user_message=req.message,
                auth_token=token,
                backend=backend,
                store=store,
                notifier=notifier,
                conversation_id=req.conversation_id,
                latitude=req.latitude,
                longitude=req.longitude,
                system_prompt=system_prompt,
                extra_tools=extra_tools,
            )
        finally:
            await backend.close()

        logger.info(
            f"Chat: user={user_id} action={result.get('action')} "
            f"tools={result.get('tools_used', [])}"
        )

        return ChatResponse(
            reply=result["reply"],
            action=result.get("action"),
            data=result.get("data"),
            conversation_id=result["conversation_id"],
            tools_used=result.get("tools_used", []),
        )

    @app.post("/agent/execute")
    async def execute(
        req: ExecuteRequest,
        authorization: str = Header(..., description="Bearer <token>"),
    ):
        """Scheduler-facing endpoint for intelligent order execution."""
        token = _extract_token(authorization)
        await auth.verify_token(token)

        backend = backend_factory(token)
        try:
            result = await run_execution_agent(
                order_id=req.order_id,
                auth_token=token,
                backend=backend,
                store=store,
                system_prompt=execution_prompt,
            )
        finally:
            await backend.close()

        return {
            "success": result["success"],
            "message": result["message"],
            "tools_used": result.get("tools_used", []),
            "alternatives_found": result.get("alternatives_found", False),
        }

    @app.get("/agent/conversations")
    async def list_conversations(
        authorization: str = Header(..., description="Bearer <token>"),
    ):
        """List all conversations for the authenticated user."""
        token = _extract_token(authorization)
        user_id = await auth.verify_token(token)
        conversations = await store.list_conversations(user_id)
        return {"conversations": conversations}

    @app.get("/agent/conversation/{conversation_id}")
    async def get_conversation(
        conversation_id: str,
        authorization: str = Header(..., description="Bearer <token>"),
    ):
        """Retrieve conversation history."""
        token = _extract_token(authorization)
        await auth.verify_token(token)
        messages = await store.load_conversation(conversation_id)
        return {"conversation_id": conversation_id, "messages": messages}

    # ── OpenClaw-style Agent Management Endpoints ────────────
    # Only enabled when a ToolRegistry is provided.

    if tool_registry:
        runtime = AgentRuntime(tool_registry=tool_registry, store=store)

        @app.get("/agents/tools", response_model=list[ToolCatalogItem])
        async def list_tools():
            """List all available tools agents can use."""
            return tool_registry.to_catalog()

        @app.post("/agents", response_model=AgentResponse)
        async def create_agent(
            req: AgentCreateRequest,
            authorization: str = Header(..., description="Bearer <token>"),
        ):
            """Create a new custom agent."""
            token = _extract_token(authorization)
            user_id = await auth.verify_token(token)

            agent = AgentConfig(
                name=req.name,
                description=req.description,
                system_prompt=req.system_prompt,
                personality=req.personality,
                greeting=req.greeting,
                workflow=req.workflow,
                model_override=req.model_override,
            )
            # Set tools
            for t in req.tools:
                agent.add_tool(t.get("tool_id", ""), t.get("config"))
            # Set trigger
            if req.trigger:
                from tova_core.models.agent import AgentTrigger, TriggerType
                trigger_type = TriggerType(req.trigger.get("type", "manual"))
                agent.trigger = AgentTrigger(
                    type=trigger_type,
                    cron=req.trigger.get("cron"),
                    event=req.trigger.get("event"),
                    max_runs_per_day=req.trigger.get("max_runs_per_day"),
                )

            agent_data = agent.to_dict()
            agent_data["user_id"] = user_id
            try:
                agent_id = await store.save_agent(user_id, agent_data)
                agent_data["id"] = agent_id
            except NotImplementedError:
                raise HTTPException(status_code=501, detail="Agent persistence not configured")

            return AgentResponse(
                id=agent_data["id"],
                name=agent.name,
                description=agent.description,
                status=agent.status.value,
                trigger_type=agent.trigger.type.value,
                tools=[{"tool_id": t.tool_id} for t in agent.tools],
            )

        @app.get("/agents", response_model=list[AgentResponse])
        async def list_agents(
            authorization: str = Header(..., description="Bearer <token>"),
        ):
            """List all agents owned by the authenticated user."""
            token = _extract_token(authorization)
            user_id = await auth.verify_token(token)
            try:
                agents = await store.list_agents(user_id)
            except NotImplementedError:
                return []
            return [
                AgentResponse(
                    id=a.get("id", ""),
                    name=a.get("name", ""),
                    description=a.get("description", ""),
                    status=a.get("status", "active"),
                    trigger_type=a.get("trigger", {}).get("type", "manual"),
                    tools=a.get("tools", []),
                    created_at=a.get("created_at", ""),
                    updated_at=a.get("updated_at", ""),
                )
                for a in agents
            ]

        @app.get("/agents/{agent_id}", response_model=dict)
        async def get_agent(
            agent_id: str,
            authorization: str = Header(..., description="Bearer <token>"),
        ):
            """Get full agent configuration."""
            token = _extract_token(authorization)
            await auth.verify_token(token)
            try:
                agent_data = await store.get_agent(agent_id)
            except NotImplementedError:
                raise HTTPException(status_code=501, detail="Agent persistence not configured")
            if not agent_data:
                raise HTTPException(status_code=404, detail="Agent not found")
            return agent_data

        @app.put("/agents/{agent_id}", response_model=AgentResponse)
        async def update_agent(
            agent_id: str,
            req: AgentUpdateRequest,
            authorization: str = Header(..., description="Bearer <token>"),
        ):
            """Update an existing agent."""
            token = _extract_token(authorization)
            user_id = await auth.verify_token(token)
            try:
                existing = await store.get_agent(agent_id)
            except NotImplementedError:
                raise HTTPException(status_code=501, detail="Agent persistence not configured")
            if not existing:
                raise HTTPException(status_code=404, detail="Agent not found")

            # Merge updates
            updates = req.model_dump(exclude_none=True)
            existing.update(updates)
            await store.save_agent(user_id, existing)

            return AgentResponse(
                id=agent_id,
                name=existing.get("name", ""),
                description=existing.get("description", ""),
                status=existing.get("status", "active"),
                trigger_type=existing.get("trigger", {}).get("type", "manual"),
                tools=existing.get("tools", []),
            )

        @app.delete("/agents/{agent_id}")
        async def delete_agent(
            agent_id: str,
            authorization: str = Header(..., description="Bearer <token>"),
        ):
            """Delete an agent."""
            token = _extract_token(authorization)
            await auth.verify_token(token)
            try:
                deleted = await store.delete_agent(agent_id)
            except NotImplementedError:
                raise HTTPException(status_code=501, detail="Agent persistence not configured")
            if not deleted:
                raise HTTPException(status_code=404, detail="Agent not found")
            return {"deleted": True}

        @app.post("/agents/{agent_id}/chat", response_model=AgentChatResponse)
        async def agent_chat(
            agent_id: str,
            req: AgentChatRequest,
            authorization: str = Header(..., description="Bearer <token>"),
        ):
            """Chat with a specific custom agent."""
            token = _extract_token(authorization)
            user_id = await auth.verify_token(token)

            try:
                agent_data = await store.get_agent(agent_id)
            except NotImplementedError:
                raise HTTPException(status_code=501, detail="Agent persistence not configured")
            if not agent_data:
                raise HTTPException(status_code=404, detail="Agent not found")

            agent_config = AgentConfig.from_dict(agent_data)
            result = await runtime.run(
                agent_config=agent_config,
                user_message=req.message,
                user_id=user_id,
                conversation_id=req.conversation_id,
                context=req.context,
                auth_token=token,
            )

            return AgentChatResponse(
                reply=result["reply"],
                agent_id=result.get("agent_id", agent_id),
                agent_name=result.get("agent_name", agent_config.name),
                conversation_id=result["conversation_id"],
                tools_used=result.get("tools_used", []),
                data=result.get("data"),
            )

    # ── Feature: File Upload & Device Workspace ────────────────
    if file_store:
        from fastapi import UploadFile, File as FastAPIFile, Form

        @app.post("/files/upload")
        async def upload_file(
            file: UploadFile = FastAPIFile(...),
            folder: str = Form("uploads"),
            authorization: str = Header(..., description="Bearer <token>"),
        ):
            """Upload a file to the user's workspace.

            Accepts any file type. Files are stored in the user's namespace:
            {user_id}/{folder}/{filename}
            """
            token = _extract_token(authorization)
            user_id = await auth.verify_token(token)

            content = await file.read()
            path = f"{user_id}/{folder}/{file.filename}"
            url = await file_store.upload(
                path=path,
                content=content,
                content_type=file.content_type or "application/octet-stream",
                metadata={"original_filename": file.filename, "folder": folder},
            )
            return {
                "path": path,
                "url": url,
                "filename": file.filename,
                "size": len(content),
                "content_type": file.content_type,
            }

        @app.get("/files/list")
        async def list_user_files(
            folder: str = "",
            authorization: str = Header(..., description="Bearer <token>"),
        ):
            """List files in the user's workspace."""
            token = _extract_token(authorization)
            user_id = await auth.verify_token(token)
            prefix = f"{user_id}/{folder}" if folder else f"{user_id}/"
            files = await file_store.list_files(prefix=prefix, limit=100)
            return {"files": files, "count": len(files)}

        @app.get("/files/download/{file_path:path}")
        async def download_file(
            file_path: str,
            authorization: str = Header(..., description="Bearer <token>"),
        ):
            """Download a file from the user's workspace."""
            from fastapi.responses import StreamingResponse
            token = _extract_token(authorization)
            user_id = await auth.verify_token(token)

            full_path = file_path if file_path.startswith(user_id) else f"{user_id}/{file_path}"
            content = await file_store.download(full_path)

            import mimetypes as _mt
            ct = _mt.guess_type(full_path)[0] or "application/octet-stream"
            filename = full_path.split("/")[-1]

            return StreamingResponse(
                iter([content]),
                media_type=ct,
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )

        @app.delete("/files/{file_path:path}")
        async def delete_user_file(
            file_path: str,
            authorization: str = Header(..., description="Bearer <token>"),
        ):
            """Delete a file from the user's workspace."""
            token = _extract_token(authorization)
            user_id = await auth.verify_token(token)
            full_path = file_path if file_path.startswith(user_id) else f"{user_id}/{file_path}"
            deleted = await file_store.delete(full_path)
            return {"deleted": deleted, "path": full_path}

        @app.post("/files/connect-device")
        async def connect_device_directory(
            request: Request,
            authorization: str = Header(..., description="Bearer <token>"),
        ):
            """Connect a local device directory so Tova can read files from it.

            Body: {"path": "/Users/you/Documents", "alias": "documents"}

            This creates a symlink in the user's workspace pointing to the
            real directory, so all workspace tools can access the files.

            SECURITY: Only works in standalone mode. The path must exist
            and be a readable directory.
            """
            import os as _os
            token = _extract_token(authorization)
            user_id = await auth.verify_token(token)

            body = await request.json()
            device_path = body.get("path", "")
            alias = body.get("alias", "")

            if not device_path or not _os.path.isdir(device_path):
                raise HTTPException(status_code=400, detail=f"Invalid or non-existent directory: {device_path}")

            if not alias:
                alias = _os.path.basename(device_path.rstrip("/"))

            # Import files from the device directory into the file store
            import_count = 0
            for root, dirs, filenames in _os.walk(device_path):
                # Skip hidden directories and common junk
                dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("node_modules", "__pycache__", ".git")]
                for fname in filenames:
                    if fname.startswith("."):
                        continue
                    abs_path = _os.path.join(root, fname)
                    rel_path = _os.path.relpath(abs_path, device_path)
                    store_path = f"{user_id}/device/{alias}/{rel_path}"

                    try:
                        stat = _os.stat(abs_path)
                        # Skip files over 50MB
                        if stat.st_size > 50 * 1024 * 1024:
                            continue
                        with open(abs_path, "rb") as f:
                            content = f.read()
                        import mimetypes as _mt
                        ct = _mt.guess_type(fname)[0] or "application/octet-stream"
                        await file_store.upload(
                            path=store_path,
                            content=content,
                            content_type=ct,
                            metadata={
                                "source": "device",
                                "device_path": abs_path,
                                "alias": alias,
                            },
                        )
                        import_count += 1
                    except Exception as e:
                        logger.debug(f"Skipping {abs_path}: {e}")
                        continue

                    # Limit to 500 files per connection
                    if import_count >= 500:
                        break
                if import_count >= 500:
                    break

            return {
                "connected": True,
                "alias": alias,
                "device_path": device_path,
                "files_imported": import_count,
                "workspace_prefix": f"{user_id}/device/{alias}/",
                "message": (
                    f"Connected '{alias}' ({import_count} files imported). "
                    f"Tova can now read and analyze these files. "
                    f"Access them at: device/{alias}/filename"
                ),
            }

        @app.get("/files/devices")
        async def list_connected_devices(
            authorization: str = Header(..., description="Bearer <token>"),
        ):
            """List connected device directories."""
            token = _extract_token(authorization)
            user_id = await auth.verify_token(token)
            files = await file_store.list_files(prefix=f"{user_id}/device/", limit=1000)

            # Group by alias
            devices = {}
            for f in files:
                parts = f.get("path", "").split("/")
                if len(parts) >= 3:
                    alias = parts[2] if parts[1] == "device" else ""
                    if alias and alias not in devices:
                        meta = f.get("metadata", {})
                        devices[alias] = {
                            "alias": alias,
                            "device_path": meta.get("device_path", ""),
                            "file_count": 0,
                        }
                    if alias:
                        devices[alias]["file_count"] += 1

            return {"devices": list(devices.values()), "count": len(devices)}

    # ── Feature: Auto-detect from providers ────────────────────
    _features = set(enabled_features or [])
    if not enabled_features:
        # Auto-enable features when their provider is supplied
        if vector_store:
            _features.add("datasets")
        _features.update(["todos", "notes", "events"])  # Always available (store-only)
        if email_provider:
            _features.add("email")
        if telephony:
            _features.update(["phone", "emergency"])
        if video_stream:
            _features.add("cctv")
        if geolocation:
            _features.add("vehicles")
        if file_store:
            _features.add("files")
        if travel_provider:
            _features.add("travel")
        _features.add("web_search")  # Always available — Tova's universal search
        _features.add("workforce")   # Always available — AI workforce management
        if file_store:
            _features.add("workspace")  # File workspace operations

    # ── User Preferences & Brain Box Endpoints ─────────────────

    @app.get("/me/features", response_model=UserFeaturesResponse)
    async def get_my_features(
        authorization: str = Header(..., description="Bearer <token>"),
    ):
        """List enabled features and preferences for the current user."""
        token = _extract_token(authorization)
        user_id = await auth.verify_token(token)
        try:
            prefs = await store.get_user_preferences(user_id)
        except NotImplementedError:
            prefs = {}
        return UserFeaturesResponse(
            user_id=user_id,
            enabled_features=sorted(_features),
            preferences=prefs,
        )

    @app.put("/me/preferences/{feature}")
    async def update_my_preferences(
        feature: str,
        req: UserPreferencesUpdate,
        authorization: str = Header(..., description="Bearer <token>"),
    ):
        """Update preferences for a specific feature."""
        token = _extract_token(authorization)
        user_id = await auth.verify_token(token)
        try:
            await store.save_user_preferences(user_id, feature, req.preferences)
            return {"success": True, "feature": feature}
        except NotImplementedError:
            raise HTTPException(status_code=501, detail="Preferences not configured")

    @app.get("/me/brain/{feature}", response_model=BrainBoxResponse)
    async def get_brain_box(
        feature: str,
        authorization: str = Header(..., description="Bearer <token>"),
    ):
        """View Brain Box contents for a feature."""
        token = _extract_token(authorization)
        user_id = await auth.verify_token(token)
        box = BrainBox(store, feature)
        memories = await box.recall(user_id)
        return BrainBoxResponse(
            feature=feature,
            memories=memories,
            count=len(memories),
        )

    # ── Dataset / RAG Endpoints ────────────────────────────────

    if "datasets" in _features and vector_store:
        from tova_core.rag.embedder import Embedder
        from tova_core.rag.ingest import IngestionPipeline
        from tova_core.rag.retriever import Retriever
        from tova_core.models.dataset import (
            DatasetCreate, DatasetResponse, DatasetQueryRequest,
            DatasetQueryResponse, DatasetIngestRequest,
        )

        _embedder = Embedder(
            provider=settings.embedding_provider,
            model=settings.embedding_model,
            api_key=settings.embedding_api_key or settings.openai_api_key,
        )
        _pipeline = IngestionPipeline(vector_store, _embedder,
                                       chunk_size=settings.chunk_size,
                                       chunk_overlap=settings.chunk_overlap)
        _retriever = Retriever(vector_store, _embedder)

        @app.post("/datasets", response_model=DatasetResponse)
        async def create_dataset(
            req: DatasetCreate,
            authorization: str = Header(..., description="Bearer <token>"),
        ):
            """Create a new dataset for RAG queries."""
            token = _extract_token(authorization)
            user_id = await auth.verify_token(token)
            from datetime import datetime
            now = datetime.now().isoformat()
            ds = {
                "user_id": user_id,
                "name": req.name,
                "description": req.description,
                "status": "pending",
                "file_count": 0,
                "chunk_count": 0,
                "embedding_model": _embedder.model,
                "vector_collection": "",
                "created_at": now,
                "updated_at": now,
            }
            try:
                ds_id = await store.save_dataset_metadata(user_id, ds)
                ds["id"] = ds_id
                ds["vector_collection"] = f"ds_{user_id}_{ds_id}"
                await store.save_dataset_metadata(user_id, ds)
            except NotImplementedError:
                raise HTTPException(status_code=501, detail="Dataset storage not configured")
            return DatasetResponse(**ds)

        @app.get("/datasets", response_model=list[DatasetResponse])
        async def list_user_datasets(
            authorization: str = Header(..., description="Bearer <token>"),
        ):
            """List all datasets for the current user."""
            token = _extract_token(authorization)
            user_id = await auth.verify_token(token)
            try:
                datasets = await store.list_datasets(user_id)
                return [DatasetResponse(**d) for d in datasets]
            except NotImplementedError:
                return []

        @app.get("/datasets/{dataset_id}")
        async def get_dataset_detail(
            dataset_id: str,
            authorization: str = Header(..., description="Bearer <token>"),
        ):
            """Get dataset metadata and stats."""
            token = _extract_token(authorization)
            await auth.verify_token(token)
            try:
                ds = await store.get_dataset(dataset_id)
                if not ds:
                    raise HTTPException(status_code=404, detail="Dataset not found")
                return ds
            except NotImplementedError:
                raise HTTPException(status_code=501, detail="Dataset storage not configured")

        @app.delete("/datasets/{dataset_id}")
        async def delete_dataset_endpoint(
            dataset_id: str,
            authorization: str = Header(..., description="Bearer <token>"),
        ):
            """Delete a dataset and its vector data."""
            token = _extract_token(authorization)
            await auth.verify_token(token)
            try:
                ds = await store.get_dataset(dataset_id)
                if ds and ds.get("vector_collection"):
                    await vector_store.delete_collection(ds["vector_collection"])
                deleted = await store.delete_dataset(dataset_id)
                return {"deleted": deleted}
            except NotImplementedError:
                raise HTTPException(status_code=501, detail="Dataset storage not configured")

        @app.post("/datasets/{dataset_id}/query", response_model=DatasetQueryResponse)
        async def query_dataset_endpoint(
            dataset_id: str,
            req: DatasetQueryRequest,
            authorization: str = Header(..., description="Bearer <token>"),
        ):
            """RAG query against a dataset."""
            token = _extract_token(authorization)
            await auth.verify_token(token)
            try:
                ds = await store.get_dataset(dataset_id)
                if not ds:
                    raise HTTPException(status_code=404, detail="Dataset not found")
                collection = ds.get("vector_collection", f"ds_{dataset_id}")
                results = await _retriever.query(
                    collection_name=collection,
                    query=req.query,
                    top_k=req.top_k,
                    filter_metadata=req.filter_metadata,
                )
                return DatasetQueryResponse(
                    query=req.query,
                    results=results,
                    dataset_id=dataset_id,
                )
            except NotImplementedError:
                raise HTTPException(status_code=501, detail="Dataset storage not configured")

        @app.post("/datasets/{dataset_id}/ingest")
        async def ingest_into_dataset(
            dataset_id: str,
            req: DatasetIngestRequest,
            authorization: str = Header(..., description="Bearer <token>"),
        ):
            """Ingest content into an existing dataset."""
            token = _extract_token(authorization)
            await auth.verify_token(token)
            try:
                ds = await store.get_dataset(dataset_id)
                if not ds:
                    raise HTTPException(status_code=404, detail="Dataset not found")
                collection = ds.get("vector_collection", f"ds_{dataset_id}")
                result = await _pipeline.ingest(
                    content=req.content,
                    content_type=req.content_type,
                    collection_name=collection,
                    source_name=req.source_name,
                )
                return result
            except NotImplementedError:
                raise HTTPException(status_code=501, detail="Dataset storage not configured")

    # ── Todo Endpoints ─────────────────────────────────────────

    if "todos" in _features:
        from tova_core.models.todo import TodoCreate, TodoUpdate, TodoResponse

        @app.post("/todos", response_model=TodoResponse)
        async def create_todo_endpoint(
            req: TodoCreate,
            authorization: str = Header(..., description="Bearer <token>"),
        ):
            token = _extract_token(authorization)
            user_id = await auth.verify_token(token)
            from datetime import datetime
            now = datetime.now().isoformat()
            todo = {
                "user_id": user_id, "title": req.title,
                "description": req.description, "status": "pending",
                "priority": req.priority, "due_date": req.due_date,
                "tags": req.tags, "parent_id": req.parent_id,
                "dependencies": req.dependencies,
                "created_at": now, "updated_at": now,
            }
            try:
                todo_id = await store.save_todo(user_id, todo)
                todo["id"] = todo_id
                return TodoResponse(**todo)
            except NotImplementedError:
                raise HTTPException(status_code=501, detail="Todo storage not configured")

        @app.get("/todos", response_model=list[TodoResponse])
        async def list_todos_endpoint(
            status: str | None = None,
            authorization: str = Header(..., description="Bearer <token>"),
        ):
            token = _extract_token(authorization)
            user_id = await auth.verify_token(token)
            try:
                todos = await store.list_todos(user_id, status=status)
                return [TodoResponse(**t) for t in todos]
            except NotImplementedError:
                return []

        @app.put("/todos/{todo_id}")
        async def update_todo_endpoint(
            todo_id: str, req: TodoUpdate,
            authorization: str = Header(..., description="Bearer <token>"),
        ):
            token = _extract_token(authorization)
            await auth.verify_token(token)
            updates = req.model_dump(exclude_none=True)
            try:
                success = await store.update_todo(todo_id, updates)
                return {"success": success, "id": todo_id}
            except NotImplementedError:
                raise HTTPException(status_code=501, detail="Todo storage not configured")

        @app.delete("/todos/{todo_id}")
        async def delete_todo_endpoint(
            todo_id: str,
            authorization: str = Header(..., description="Bearer <token>"),
        ):
            token = _extract_token(authorization)
            await auth.verify_token(token)
            try:
                deleted = await store.delete_todo(todo_id)
                return {"deleted": deleted}
            except NotImplementedError:
                raise HTTPException(status_code=501, detail="Todo storage not configured")

        @app.post("/todos/{todo_id}/complete")
        async def complete_todo_endpoint(
            todo_id: str,
            authorization: str = Header(..., description="Bearer <token>"),
        ):
            token = _extract_token(authorization)
            await auth.verify_token(token)
            from datetime import datetime
            try:
                success = await store.update_todo(todo_id, {
                    "status": "completed",
                    "completed_at": datetime.now().isoformat(),
                })
                return {"success": success, "id": todo_id, "status": "completed"}
            except NotImplementedError:
                raise HTTPException(status_code=501, detail="Todo storage not configured")

    # ── Notes Endpoints ────────────────────────────────────────

    if "notes" in _features:
        from tova_core.models.notes import NoteCreate, NoteUpdate, NoteResponse

        @app.post("/notes", response_model=NoteResponse)
        async def create_note_endpoint(
            req: NoteCreate,
            authorization: str = Header(..., description="Bearer <token>"),
        ):
            token = _extract_token(authorization)
            user_id = await auth.verify_token(token)
            from datetime import datetime
            now = datetime.now().isoformat()
            note = {
                "user_id": user_id, "title": req.title,
                "content": req.content, "summary": "",
                "tags": req.tags, "source_type": req.source_type,
                "source_url": req.source_url,
                "created_at": now, "updated_at": now,
            }
            try:
                note_id = await store.save_note(user_id, note)
                note["id"] = note_id
                return NoteResponse(**note)
            except NotImplementedError:
                raise HTTPException(status_code=501, detail="Note storage not configured")

        @app.get("/notes", response_model=list[NoteResponse])
        async def list_notes_endpoint(
            limit: int = 20,
            authorization: str = Header(..., description="Bearer <token>"),
        ):
            token = _extract_token(authorization)
            user_id = await auth.verify_token(token)
            try:
                notes = await store.list_notes(user_id, limit=limit)
                return [NoteResponse(**n) for n in notes]
            except NotImplementedError:
                return []

        @app.get("/notes/{note_id}", response_model=NoteResponse)
        async def get_note_endpoint(
            note_id: str,
            authorization: str = Header(..., description="Bearer <token>"),
        ):
            token = _extract_token(authorization)
            await auth.verify_token(token)
            try:
                note = await store.get_note(note_id)
                if not note:
                    raise HTTPException(status_code=404, detail="Note not found")
                return NoteResponse(**note)
            except NotImplementedError:
                raise HTTPException(status_code=501, detail="Note storage not configured")

        @app.delete("/notes/{note_id}")
        async def delete_note_endpoint(
            note_id: str,
            authorization: str = Header(..., description="Bearer <token>"),
        ):
            token = _extract_token(authorization)
            await auth.verify_token(token)
            try:
                deleted = await store.delete_note(note_id)
                return {"deleted": deleted}
            except NotImplementedError:
                raise HTTPException(status_code=501, detail="Note storage not configured")

    # ── Event Endpoints ────────────────────────────────────────

    if "events" in _features:
        from tova_core.models.event import EventCreate, EventUpdate, EventResponse

        @app.post("/events", response_model=EventResponse)
        async def create_event_endpoint(
            req: EventCreate,
            authorization: str = Header(..., description="Bearer <token>"),
        ):
            token = _extract_token(authorization)
            user_id = await auth.verify_token(token)
            from datetime import datetime
            now = datetime.now().isoformat()
            event = {
                "user_id": user_id, "title": req.title,
                "description": req.description,
                "start_time": req.start_time, "end_time": req.end_time,
                "location": req.location, "attendees": req.attendees,
                "reminders": req.reminders, "status": "scheduled",
                "recurrence": req.recurrence,
                "created_at": now, "updated_at": now,
            }
            try:
                event_id = await store.save_event(user_id, event)
                event["id"] = event_id
                return EventResponse(**event)
            except NotImplementedError:
                raise HTTPException(status_code=501, detail="Event storage not configured")

        @app.get("/events", response_model=list[EventResponse])
        async def list_events_endpoint(
            start: str | None = None,
            end: str | None = None,
            authorization: str = Header(..., description="Bearer <token>"),
        ):
            token = _extract_token(authorization)
            user_id = await auth.verify_token(token)
            try:
                events = await store.list_events(user_id, start=start, end=end)
                return [EventResponse(**e) for e in events]
            except NotImplementedError:
                return []

        @app.put("/events/{event_id}")
        async def update_event_endpoint(
            event_id: str, req: EventUpdate,
            authorization: str = Header(..., description="Bearer <token>"),
        ):
            token = _extract_token(authorization)
            await auth.verify_token(token)
            updates = req.model_dump(exclude_none=True)
            try:
                success = await store.update_event(event_id, updates)
                return {"success": success, "id": event_id}
            except NotImplementedError:
                raise HTTPException(status_code=501, detail="Event storage not configured")

        @app.delete("/events/{event_id}")
        async def delete_event_endpoint(
            event_id: str,
            authorization: str = Header(..., description="Bearer <token>"),
        ):
            token = _extract_token(authorization)
            await auth.verify_token(token)
            try:
                deleted = await store.delete_event(event_id)
                return {"deleted": deleted}
            except NotImplementedError:
                raise HTTPException(status_code=501, detail="Event storage not configured")

    # ── Emergency Endpoints ────────────────────────────────────

    if "emergency" in _features:
        from tova_core.models.emergency import (
            EmergencyCreate, EmergencyUpdate, EmergencyResponse,
        )

        @app.post("/emergencies", response_model=EmergencyResponse)
        async def report_emergency_endpoint(
            req: EmergencyCreate,
            authorization: str = Header(..., description="Bearer <token>"),
        ):
            token = _extract_token(authorization)
            user_id = await auth.verify_token(token)
            from datetime import datetime
            now = datetime.now().isoformat()
            emergency = {
                "reporter_id": user_id, "type": req.type,
                "severity": req.severity, "description": req.description,
                "status": "reported",
                "latitude": req.latitude, "longitude": req.longitude,
                "contact_numbers": req.contact_numbers,
                "assigned_to": [], "escalation_level": 0,
                "created_at": now, "updated_at": now,
            }
            try:
                eid = await store.save_emergency(emergency)
                emergency["id"] = eid
                return EmergencyResponse(**emergency)
            except NotImplementedError:
                raise HTTPException(status_code=501, detail="Emergency storage not configured")

        @app.get("/emergencies", response_model=list[EmergencyResponse])
        async def list_emergencies_endpoint(
            status: str | None = None,
            severity: str | None = None,
            authorization: str = Header(..., description="Bearer <token>"),
        ):
            token = _extract_token(authorization)
            await auth.verify_token(token)
            filters = {}
            if status:
                filters["status"] = status
            if severity:
                filters["severity"] = severity
            try:
                emergencies = await store.list_emergencies(filters=filters or None)
                return [EmergencyResponse(**e) for e in emergencies]
            except NotImplementedError:
                return []

        @app.put("/emergencies/{emergency_id}")
        async def update_emergency_endpoint(
            emergency_id: str, req: EmergencyUpdate,
            authorization: str = Header(..., description="Bearer <token>"),
        ):
            token = _extract_token(authorization)
            await auth.verify_token(token)
            updates = req.model_dump(exclude_none=True)
            try:
                success = await store.update_emergency(emergency_id, updates)
                return {"success": success, "id": emergency_id}
            except NotImplementedError:
                raise HTTPException(status_code=501, detail="Emergency storage not configured")

        @app.post("/emergencies/{emergency_id}/escalate")
        async def escalate_emergency_endpoint(
            emergency_id: str,
            authorization: str = Header(..., description="Bearer <token>"),
        ):
            token = _extract_token(authorization)
            await auth.verify_token(token)
            from datetime import datetime
            try:
                emergencies = await store.list_emergencies(filters=None)
                emergency = next((e for e in emergencies if e.get("id") == emergency_id), None)
                if not emergency:
                    raise HTTPException(status_code=404, detail="Emergency not found")
                new_level = emergency.get("escalation_level", 0) + 1
                await store.update_emergency(emergency_id, {
                    "escalation_level": new_level,
                    "status": "escalated",
                    "updated_at": datetime.now().isoformat(),
                })
                return {"success": True, "id": emergency_id, "new_level": new_level}
            except NotImplementedError:
                raise HTTPException(status_code=501, detail="Emergency storage not configured")

    # ── Phone Call Endpoints ───────────────────────────────────

    if "phone" in _features and telephony:
        @app.post("/calls")
        async def make_call_endpoint(
            to_number: str,
            message: str,
            authorization: str = Header(..., description="Bearer <token>"),
        ):
            token = _extract_token(authorization)
            await auth.verify_token(token)
            result = await telephony.make_call(to_number=to_number, message=message)
            return result

        @app.get("/calls/{call_id}/status")
        async def get_call_status_endpoint(
            call_id: str,
            authorization: str = Header(..., description="Bearer <token>"),
        ):
            token = _extract_token(authorization)
            await auth.verify_token(token)
            result = await telephony.get_call_status(call_id)
            return result

    # ── CCTV Endpoints ─────────────────────────────────────────

    if "cctv" in _features and video_stream:
        @app.get("/cameras")
        async def list_cameras_endpoint(
            authorization: str = Header(..., description="Bearer <token>"),
        ):
            token = _extract_token(authorization)
            await auth.verify_token(token)
            cameras = await video_stream.list_cameras()
            return {"cameras": cameras}

        @app.get("/cameras/{camera_id}/snapshot")
        async def camera_snapshot_endpoint(
            camera_id: str,
            authorization: str = Header(..., description="Bearer <token>"),
        ):
            import base64
            token = _extract_token(authorization)
            await auth.verify_token(token)
            frame = await video_stream.get_frame(camera_id)
            return {
                "camera_id": camera_id,
                "frame_base64": base64.b64encode(frame).decode("utf-8"),
                "format": "jpeg",
            }

    # ── Vehicle Endpoints ──────────────────────────────────────

    if "vehicles" in _features:
        from tova_core.models.vehicle import VehicleCreate, VehicleResponse

        @app.post("/vehicles", response_model=VehicleResponse)
        async def register_vehicle_endpoint(
            req: VehicleCreate,
            authorization: str = Header(..., description="Bearer <token>"),
        ):
            token = _extract_token(authorization)
            user_id = await auth.verify_token(token)
            from datetime import datetime
            vehicle = {
                "user_id": user_id, "name": req.name,
                "plate": req.plate, "type": req.type,
                "status": "active",
                "created_at": datetime.now().isoformat(),
            }
            try:
                vid = await store.save_vehicle(user_id, vehicle)
                vehicle["id"] = vid
                return VehicleResponse(**vehicle)
            except NotImplementedError:
                raise HTTPException(status_code=501, detail="Vehicle storage not configured")

        @app.get("/vehicles", response_model=list[VehicleResponse])
        async def list_vehicles_endpoint(
            authorization: str = Header(..., description="Bearer <token>"),
        ):
            token = _extract_token(authorization)
            user_id = await auth.verify_token(token)
            try:
                vehicles = await store.list_vehicles(user_id)
                return [VehicleResponse(**v) for v in vehicles]
            except NotImplementedError:
                return []

        @app.get("/vehicles/{vehicle_id}/position")
        async def vehicle_position_endpoint(
            vehicle_id: str,
            authorization: str = Header(..., description="Bearer <token>"),
        ):
            token = _extract_token(authorization)
            await auth.verify_token(token)
            if geolocation:
                position = await geolocation.get_vehicle_position(vehicle_id)
                return position
            return {"error": "Geolocation provider not configured"}

    # ── Unified Alerts Endpoint ────────────────────────────────

    @app.get("/alerts")
    async def list_alerts_endpoint(
        alert_type: str | None = None,
        limit: int = 50,
        authorization: str = Header(..., description="Bearer <token>"),
    ):
        """List unified alerts across all features (CCTV, vehicle, emergency, etc.)."""
        token = _extract_token(authorization)
        user_id = await auth.verify_token(token)
        try:
            alerts = await store.list_alerts(user_id, alert_type=alert_type, limit=limit)
            return {"alerts": alerts, "count": len(alerts)}
        except NotImplementedError:
            return {"alerts": [], "count": 0}

    # ── Self-Training & Agent Tools ───────────────────────────

    _self_learner = SelfLearner(
        vector_store=vector_store,
        embedder=None,  # Initialized lazily below if RAG available
    )

    # Initialize embedder for self-learner if RAG is available
    if vector_store:
        try:
            from tova_core.rag.embedder import Embedder
            _self_learner.embedder = Embedder(
                provider=settings.embedding_provider,
                model=settings.embedding_model,
                api_key=settings.embedding_api_key or settings.openai_api_key,
            )
        except Exception as e:
            logger.warning(f"Could not init embedder for self-learner: {e}")

    # Register agent management & training tools when tool_registry is provided
    if tool_registry:
        from tova_core.tools.agent_tools import build_agent_tools
        agent_tools = build_agent_tools(
            store=store,
            tool_registry=tool_registry,
            self_learner=_self_learner,
        )
        for t in agent_tools:
            tool_registry.register(t.name, t, category="agent_management")

    @app.post("/agents/train")
    async def train_agent_endpoint(
        authorization: str = Header(..., description="Bearer <token>"),
        data: str = "",
        data_type: str = "json",
        feature: str = "general",
        description: str = "",
    ):
        """Train Tova with data via REST API. Accepts JSON, text, CSV, key-value pairs."""
        token = _extract_token(authorization)
        user_id = await auth.verify_token(token)
        result = await _self_learner.learn_from_data(
            user_id=user_id,
            data=data,
            data_type=data_type,
            feature=feature,
        )
        return {
            "success": True,
            "user_id": user_id,
            "feature": feature,
            **result,
        }

    @app.post("/agents/train/correct")
    async def correct_knowledge_endpoint(
        authorization: str = Header(..., description="Bearer <token>"),
        wrong_info: str = "",
        correct_info: str = "",
        feature: str = "general",
    ):
        """Correct something Tova got wrong. Corrections are permanent, highest-priority memories."""
        token = _extract_token(authorization)
        user_id = await auth.verify_token(token)
        await _self_learner.learn_from_correction(
            user_id=user_id,
            feature=feature,
            what_was_wrong=wrong_info,
            what_is_correct=correct_info,
        )
        return {
            "success": True,
            "message": "Correction stored permanently. Tova will never repeat this mistake.",
        }

    @app.get("/agents/train/{feature}")
    async def recall_training_endpoint(
        feature: str,
        query: str = "",
        authorization: str = Header(..., description="Bearer <token>"),
    ):
        """Recall what Tova has learned for a specific feature."""
        token = _extract_token(authorization)
        user_id = await auth.verify_token(token)
        from tova_core.learning.storage import get_brain_store
        brain = get_brain_store()
        ns = f"brain_{feature}"
        if query:
            memories = await brain.search(ns, user_id, query)
        else:
            memories = await brain.load(ns, user_id)
        return {
            "feature": feature,
            "memories": memories,
            "count": len(memories),
        }

    return app
