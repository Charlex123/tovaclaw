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

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from tova_core.config import get_settings
from tova_core.models.schemas import ChatRequest, ChatResponse, ExecuteRequest, HealthResponse
from tova_core.providers.backend import BaseBackend
from tova_core.providers.store import BaseStore
from tova_core.providers.auth import BaseAuth
from tova_core.providers.notifier import BaseNotifier
from tova_core.agents.order_agent import run_order_agent
from tova_core.agents.execution_agent import run_execution_agent

logger = logging.getLogger(__name__)


def create_app(
    backend_factory: Callable[[str | None], BaseBackend],
    store: BaseStore,
    auth: BaseAuth,
    notifier: BaseNotifier | None = None,
    system_prompt: str | None = None,
    execution_prompt: str | None = None,
    cors_origins: list[str] | None = None,
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
        description="AI agent for healthcare order automation",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def _extract_token(authorization: str) -> str:
        if not authorization.startswith("Bearer "):
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

    return app
