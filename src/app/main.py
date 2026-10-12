from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.api.webhook import router
from app.core.config import load_settings, require_server
from app.core.logging import configure_logging
from app.services.runner import install_runtime, lifespan


def create_app(*, start_background: bool = True) -> FastAPI:
    settings = load_settings()
    if start_background:
        require_server(settings)
    configure_logging(settings.LOG_LEVEL)
    application = FastAPI(title="Scribe", version="0.3.0", lifespan=lifespan)
    application.state.start_background = start_background
    install_runtime(application, settings)
    application.include_router(router)

    @application.get("/health")
    async def health() -> JSONResponse:
        return JSONResponse({"status": "ok", "mailbox": settings.MAILBOX_ADDRESS})

    return application


app = create_app()
