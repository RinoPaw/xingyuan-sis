from __future__ import annotations

import os
from pathlib import Path
import secrets

from flask import Flask, jsonify, request, send_from_directory, url_for
from werkzeug.middleware.proxy_fix import ProxyFix

from ..auth import auth_dir
from ..bootstrap import ensure_default_state
from ..database import DB_PATH


_ELEMENT_SLUGS = {
    "风": "wind",
    "水": "water",
    "火": "fire",
    "雷": "bolt",
    "岩": "stone",
    "光": "light",
}


def _persistent_secret() -> str:
    configured = os.environ.get("XINGYUAN_SECRET_KEY")
    if configured:
        return configured
    path = auth_dir() / "web-secret"
    try:
        value = path.read_text(encoding="utf-8").strip()
        if len(value) >= 32:
            return value
    except FileNotFoundError:
        pass
    value = secrets.token_hex(32)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(value, encoding="utf-8")
    try:
        os.chmod(temporary, 0o600)
    except OSError:
        pass
    temporary.replace(path)
    return value


def create_app(db_path: Path | str | None = None, *, demo: bool | None = None) -> Flask:
    configured_db = db_path or os.environ.get("XINGYUAN_DB_PATH") or DB_PATH
    resolved_db = Path(configured_db).expanduser().resolve()
    ensure_default_state(resolved_db)
    demo_mode = (
        os.environ.get("XINGYUAN_DEMO_MODE", "").lower() in {"1", "true", "yes"}
        if demo is None
        else demo
    )

    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
        static_url_path="/static",
    )
    prefix = "/" + os.environ.get("XINGYUAN_URL_PREFIX", "").strip("/")
    app.config.update(
        DB_PATH=str(resolved_db),
        DEMO_MODE=demo_mode,
        MAX_CONTENT_LENGTH=2 * 1024 * 1024,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_NAME="xingyuan_session" if prefix != "/" else "session",
        SESSION_COOKIE_PATH=prefix,
        APPLICATION_ROOT=prefix,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("XINGYUAN_HTTPS", "") == "1",
    )
    app.secret_key = _persistent_secret()
    if os.environ.get("XINGYUAN_TRUST_PROXY") == "1":
        # Deployment binds only to loopback; nginx supplies these headers.
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_prefix=1)

    from .views import bp

    app.register_blueprint(bp)

    @app.get("/healthz")
    def healthz():
        return jsonify(status="ok", demo=demo_mode)

    @app.get("/assets/fonts/<path:filename>")
    def font_asset(filename: str):
        font_dir = Path(__file__).resolve().parent.parent / "gui" / "assets" / "fonts"
        return send_from_directory(font_dir, filename, max_age=86400)

    @app.template_filter("element_slug")
    def element_slug(value: str | None) -> str:
        return _ELEMENT_SLUGS.get(value or "", "unknown")

    @app.template_filter("score_text")
    def score_text(value: float | None) -> str:
        if value is None:
            return "待评"
        return f"{value:g}"

    @app.template_global()
    def page_url(page: int) -> str:
        values = request.args.to_dict(flat=True)
        # Moving to another page intentionally leaves the selected record and
        # dialog re-open flags behind, while search/filter state stays intact.
        reset_fields = {
            "web.students": ("student_no",),
            "web.courses": ("course_code",),
            "web.grades": ("id",),
            "web.notices": ("id",),
        }.get(request.endpoint or "", ())
        for name in (*reset_fields, "create", "edit"):
            values.pop(name, None)
        values["page"] = page
        return url_for(request.endpoint or "web.dashboard", **values)

    @app.template_global()
    def record_url(target: str | None = None, **changes: object) -> str:
        """Build a same-state link for a list record.

        Existing query parameters (search, filters, page) are preserved. Empty
        changes remove the corresponding key so links stay canonical.
        """
        values = request.args.to_dict(flat=True)
        for name in ("create", "edit"):
            values.pop(name, None)
        for name, value in changes.items():
            if value is None or value == "":
                values.pop(name, None)
            else:
                values[name] = str(value)
        endpoint = target or request.endpoint or "web.dashboard"
        return url_for(endpoint, **values)

    return app


def run(
    db_path: Path | str | None = None,
    *,
    host: str = "127.0.0.1",
    port: int = 3000,
    debug: bool = False,
) -> None:
    create_app(db_path).run(host=host, port=port, debug=debug)


__all__ = ["create_app", "run"]
