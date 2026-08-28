"""Application entry point — FastAPI app factory.

Modular monolith: module boundaries are explicit routers (§2); each module
can later be extracted into its own service without schema changes.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from ..app import __version__
from .config import get_settings
from .modules import (
    audit_api, auth, backup_api, base_data, bulk_charge, bulk_import,
    calibration, checklists, dashboard, equipment, events_api, files,
    health, messages, notifications_api, parts, plans, reports, requests,
    risks, search, selen, suppliers, users, workorders,
)

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"

# Persian labels for common validated fields (used in 422 translation).
_FIELD_FA = {
    "year": "سال ساخت", "name": "نام", "code": "کد", "version": "نسخه رکورد",
    "criticality": "درجه اهمیت", "status": "وضعیت", "interval_days": "دوره (روز)",
    "probability": "احتمال وقوع", "impact": "شدت اثر", "quantity": "تعداد",
    "password": "گذرواژه", "username": "نام کاربری", "score": "امتیاز",
    "duration_minutes": "مدت زمان (دقیقه)", "interval": "تناوب",
}


def _fa_number(n) -> str:
    return str(n).translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))


def _translate_validation_error(err: dict) -> str:
    """Translate one pydantic error into a human-readable Persian message."""
    t = err.get("type", "")
    ctx = err.get("ctx") or {}
    if t == "greater_than_equal":
        return f"باید بزرگ‌تر یا مساوی {_fa_number(ctx.get('ge'))} باشد"
    if t == "less_than_equal":
        return f"باید کوچک‌تر یا مساوی {_fa_number(ctx.get('le'))} باشد"
    if t == "int_parsing" or t == "int_type":
        return "باید عدد معتبر باشد"
    if t == "string_too_short":
        return f"حداقل {_fa_number(ctx.get('min_length'))} نویسه لازم است"
    if t == "string_too_long":
        return f"حداکثر {_fa_number(ctx.get('max_length'))} نویسه مجاز است"
    if t == "missing":
        return "الزامی است"
    if t == "value_error":
        return str(ctx.get("error") or "مقدار نامعتبر است")
    return "مقدار نامعتبر است"


def create_app() -> FastAPI:
    settings = get_settings()
    settings.ensure_dirs()

    app = FastAPI(
        title="BASPAR Intelligent CMMS/EAM",
        version=__version__,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
    )

    @app.exception_handler(RequestValidationError)
    async def fa_validation_handler(request: Request, exc: RequestValidationError):
        """422 responses must be readable: Persian messages instead of raw
        pydantic English dumps (root cause of the misleading
        «خطا در اتصال به سرور» toasts on the frontend)."""
        errors = []
        for err in exc.errors():
            loc = [str(x) for x in err.get("loc", []) if x not in ("body", "query", "path")]
            field = loc[-1] if loc else ""
            label = _FIELD_FA.get(field, field)
            errors.append({
                "field": field,
                "label": label,
                "message": (f"{label}: " if label else "") + _translate_validation_error(err),
                "type": err.get("type"),
            })
        first = errors[0]["message"] if len(errors) == 1 else \
            "؛ ".join(e["message"] for e in errors)
        return JSONResponse(status_code=422, content={"detail": errors, "message": first})

    @app.middleware("http")
    async def no_cache_statics(request, call_next):
        """Never let proxies/browsers cache the SPA or its modules —
        a stale JS file once blanked the whole app."""
        response = await call_next(request)
        path = request.url.path
        if path == "/" or path.startswith("/assets"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],          # Bearer-token auth; no cookies in use
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    api = settings.api_prefix
    app.include_router(auth.router, prefix=api)
    app.include_router(users.router, prefix=api)
    app.include_router(base_data.router, prefix=api)
    app.include_router(equipment.router, prefix=api)
    app.include_router(bulk_import.router, prefix=api)
    app.include_router(bulk_charge.router, prefix=api)
    app.include_router(plans.router, prefix=api)
    app.include_router(requests.router, prefix=api)
    app.include_router(workorders.router, prefix=api)
    app.include_router(notifications_api.router, prefix=api)
    app.include_router(selen.router, prefix=api)
    app.include_router(checklists.router, prefix=api)
    app.include_router(risks.router, prefix=api)
    app.include_router(calibration.router, prefix=api)
    app.include_router(parts.router, prefix=api)
    app.include_router(suppliers.router, prefix=api)
    app.include_router(messages.router, prefix=api)
    app.include_router(reports.router, prefix=api)
    app.include_router(dashboard.router, prefix=api)
    app.include_router(search.router, prefix=api)
    app.include_router(audit_api.router, prefix=api)
    app.include_router(files.router, prefix=api)
    app.include_router(backup_api.router, prefix=api)
    app.include_router(health.router, prefix=api)
    app.include_router(events_api.router, prefix=api)

    # ------------------------------------------------------------------
    # Frontend (static, RTL-native SPA) — hash-routed, no build step.
    # ------------------------------------------------------------------
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIR / "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def spa(request: Request, full_path: str):
        if full_path.startswith("api/"):
            return JSONResponse({"detail": "Not found"}, status_code=404)
        return FileResponse(FRONTEND_DIR / "index.html")

    return app


app = create_app()
