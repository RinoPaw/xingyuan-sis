from __future__ import annotations

from functools import wraps
import hmac
import math
import secrets
import sqlite3
from typing import Any, Callable, TypeVar

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from ..auth import (
    Identity,
    authenticate,
    change_password,
    has_admin,
    initialize_admin,
)
from ..reports import class_student_counts, course_score_stats, element_distribution
from ..service import XingyuanService


bp = Blueprint("web", __name__)
_PUBLIC_ENDPOINTS = {"web.login", "web.setup", "web.demo_login"}
_PASSWORD_ENDPOINTS = {"web.password", "web.logout"}
T = TypeVar("T", bound=Callable[..., Any])


def service() -> XingyuanService:
    if "service" not in g:
        g.service = XingyuanService(current_app.config["DB_PATH"])
    return g.service


def csrf_token() -> str:
    token = session.get("_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token
    return token


def _store_identity(identity: Identity) -> None:
    session.clear()
    session["identity"] = {
        "username": identity.username,
        "role": identity.role,
        "student_no": identity.student_no,
        "must_change_password": identity.must_change_password,
    }
    session["_csrf_token"] = secrets.token_urlsafe(32)


def _load_identity() -> Identity | None:
    data = session.get("identity")
    if not isinstance(data, dict):
        return None
    try:
        return Identity(
            username=str(data["username"]),
            role=str(data["role"]),
            student_no=data.get("student_no"),
            must_change_password=bool(data.get("must_change_password", False)),
        )
    except KeyError:
        session.clear()
        return None


@bp.before_request
def protect_request():
    g.identity = _load_identity()
    endpoint = request.endpoint or ""

    if request.method == "POST":
        expected = session.get("_csrf_token", "")
        supplied = request.form.get("_csrf_token", "") or request.headers.get("X-CSRF-Token", "")
        if not expected or not supplied or not hmac.compare_digest(expected, supplied):
            abort(400, "页面已过期，请刷新后重试")

    if endpoint in _PUBLIC_ENDPOINTS:
        return None
    if g.identity is None:
        return redirect(url_for("web.login", next=request.path))
    if g.identity.must_change_password and endpoint not in _PASSWORD_ENDPOINTS:
        flash("首次登录需要先设置新密码", "info")
        return redirect(url_for("web.password"))
    return None


@bp.context_processor
def template_context():
    identity = g.get("identity") or _load_identity()
    navigation = [
        ("web.dashboard", "campus", "校园总览", "CAMPUS"),
        ("web.students", "students", "学生名册", "ROSTER"),
        ("web.courses", "courses", "课程矩阵", "COURSES"),
        ("web.grades", "grades", "成绩记录", "SCORES"),
        ("web.notices", "notices", "班级公告", "NOTICES"),
    ]
    return {
        "identity": identity,
        "navigation": navigation,
        "csrf_token": csrf_token,
        "demo_mode": current_app.config["DEMO_MODE"],
        "has_admin": has_admin(),
    }


def admin_required(view: T) -> T:
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.identity is None or not g.identity.is_admin:
            abort(403)
        return view(*args, **kwargs)

    return wrapped  # type: ignore[return-value]


def _paginate(
    items: list[Any],
    per_page: int,
    selected_index: int | None = None,
) -> tuple[list[Any], dict[str, Any]]:
    total = len(items)
    pages = max(1, math.ceil(total / per_page))
    try:
        page = int(request.args.get("page", 1))
    except ValueError:
        page = 1
    if selected_index is not None:
        # An explicit record wins over a stale page number. Direct links and
        # links from another page therefore always show a highlighted record.
        page = selected_index // per_page + 1
    page = min(max(page, 1), pages)
    start = (page - 1) * per_page
    return items[start : start + per_page], {
        "page": page,
        "pages": pages,
        "total": total,
        "has_prev": page > 1,
        "has_next": page < pages,
        "prev": page - 1,
        "next": page + 1,
    }


# Only non-sensitive, explicitly declared fields are kept as one-shot drafts.
# Passwords, CSRF tokens, and hidden routing fields are never persisted.
_FORM_DRAFT_FIELDS = {
    "new-student": (
        "student_no", "name", "family", "branch", "enrollment_year", "class_code",
        "gender", "birth_date", "age", "status", "primary_element",
        "primary_affinity", "contact", "dormitory", "notes",
    ),
    "edit-student": (
        "family", "branch", "enrollment_year", "class_code", "gender", "birth_date",
        "age", "status", "primary_element", "primary_affinity", "contact",
        "dormitory", "notes",
    ),
    "new-course": ("course_code", "name", "department_code", "credits", "hours"),
    "edit-course": ("name", "department_code", "credits", "hours"),
    "new-grade": ("student_no", "course_code", "semester", "score"),
    "edit-grade": ("semester", "score"),
    "new-notice": ("class_code", "title", "body"),
}
_DRAFT_TEXT_LIMIT = 800
_DRAFT_MESSAGE_LIMIT = 300
# Flask's signed session cookie is small. Keep the complete one-shot draft
# comfortably below the browser cookie limit, even after URL-safe encoding.
_DRAFT_TOTAL_LIMIT = 2800


def _save_form_draft(dialog: str, error: Exception) -> None:
    fields = _FORM_DRAFT_FIELDS.get(dialog)
    if fields is None:
        return
    values: dict[str, str] = {}
    used = 0
    for name in fields:
        remaining = _DRAFT_TOTAL_LIMIT - used
        value = request.form.get(name, "")[: min(_DRAFT_TEXT_LIMIT, max(remaining, 0))]
        values[name] = value
        used += len(value)
    message = str(error)[:_DRAFT_MESSAGE_LIMIT]
    drafts = dict(session.get("_form_drafts") or {})
    drafts[dialog] = {
        "message": message,
        "values": values,
    }
    session["_form_drafts"] = drafts
    session.modified = True


def _clear_form_draft(dialog: str) -> None:
    drafts = session.get("_form_drafts")
    if isinstance(drafts, dict) and dialog in drafts:
        drafts.pop(dialog)
        session["_form_drafts"] = drafts
        session.modified = True


def _consume_form_drafts() -> dict[str, dict[str, Any]]:
    raw = session.pop("_form_drafts", None)
    drafts: dict[str, dict[str, Any]] = {}
    if not isinstance(raw, dict):
        return drafts
    for dialog, data in raw.items():
        if not isinstance(data, dict):
            continue
        message = data.get("message", "")
        values = data.get("values", {})
        drafts[str(dialog)] = {
            "message": str(message)[:_DRAFT_MESSAGE_LIMIT],
            "values": {
                str(name): str(value)[:_DRAFT_TEXT_LIMIT]
                for name, value in values.items()
                if isinstance(name, str) and isinstance(value, str)
            },
        }
    if raw:
        session.modified = True
    return drafts


def _form_int(name: str, *, optional: bool = False) -> int | None:
    value = request.form.get(name, "").strip()
    if optional and not value:
        return None
    return int(value)


def _form_float(name: str, *, optional: bool = False) -> float | None:
    value = request.form.get(name, "").strip()
    if optional and not value:
        return None
    return float(value)


def _optional_form(name: str) -> str | None:
    value = request.form.get(name, "").strip()
    return value or None


def _mutation_error(error: Exception) -> None:
    flash(str(error), "error")


@bp.route("/login", methods=("GET", "POST"))
def login():
    if g.identity is not None:
        return redirect(url_for("web.dashboard"))
    username = request.form.get("username", "").strip() if request.method == "POST" else ""
    if request.method == "POST":
        identity = authenticate(
            current_app.config["DB_PATH"],
            username,
            request.form.get("password", ""),
        )
        if identity is None:
            flash("账号或密码不正确，请重新核对", "error")
        else:
            _store_identity(identity)
            flash("身份确认，欢迎回到星原", "success")
            return redirect(url_for("web.password" if identity.must_change_password else "web.dashboard"))
    return render_template("login.html", username=username)


@bp.route("/setup", methods=("GET", "POST"))
def setup():
    if has_admin():
        return redirect(url_for("web.login"))
    if request.method == "POST":
        password = request.form.get("password", "")
        if password != request.form.get("confirm_password", ""):
            flash("两次输入的密码不一致", "error")
        else:
            try:
                identity = initialize_admin(password)
                if request.form.get("seed") == "1" and not service().list_students():
                    service().seed_demo()
                _store_identity(identity)
                flash("管理员已初始化，校园终端准备完成", "success")
                return redirect(url_for("web.dashboard"))
            except (ValueError, sqlite3.Error, OSError) as error:
                _mutation_error(error)
    return render_template("setup.html")


@bp.post("/demo")
def demo_login():
    if not current_app.config["DEMO_MODE"] or not has_admin():
        abort(404)
    _store_identity(Identity("Administrator", "admin"))
    return redirect(url_for("web.dashboard"))


@bp.post("/logout")
def logout():
    session.clear()
    flash("已安全退出当前账号", "info")
    return redirect(url_for("web.login"))


@bp.route("/password", methods=("GET", "POST"))
def password():
    if request.method == "POST":
        identity: Identity = g.identity
        current = authenticate(
            current_app.config["DB_PATH"], identity.username, request.form.get("current_password", "")
        )
        new_password = request.form.get("new_password", "")
        if current is None:
            flash("当前密码不正确", "error")
        elif new_password != request.form.get("confirm_password", ""):
            flash("两次输入的新密码不一致", "error")
        else:
            try:
                updated = change_password(current_app.config["DB_PATH"], identity, new_password)
                _store_identity(updated)
                flash("密码已更新", "success")
                return redirect(url_for("web.dashboard"))
            except (ValueError, sqlite3.Error, OSError) as error:
                _mutation_error(error)
    return render_template("password.html")


@bp.get("/")
def dashboard():
    svc = service()
    identity: Identity = g.identity
    announcements = svc.list_announcements(
        None if identity.is_admin else identity.student_no
    )[:4]
    if identity.is_student:
        student = svc.student_by_no(str(identity.student_no))
        enrollments = svc.enrollments_for_student(str(identity.student_no))
        scores = [float(row["score"]) for row in enrollments if row["score"] is not None]
        return render_template(
            "dashboard.html",
            student=student,
            enrollments=enrollments[:5],
            announcements=announcements,
            stats={
                "courses": len(enrollments),
                "average_score": round(sum(scores) / len(scores), 1) if scores else None,
                "graded": len(scores),
                "pending": len(enrollments) - len(scores),
            },
            elements=[],
            course_stats=[],
            recent_students=[],
            class_counts=[],
        )

    stats = svc.stats()
    elements = element_distribution(svc.db_path)
    course_stats = sorted(
        course_score_stats(svc.db_path),
        key=lambda row: row["average_score"] or 0,
        reverse=True,
    )[:5]
    return render_template(
        "dashboard.html",
        student=None,
        enrollments=svc.list_enrollments()[:5],
        announcements=announcements,
        stats=stats,
        elements=elements,
        course_stats=course_stats,
        recent_students=svc.list_students()[:6],
        class_counts=class_student_counts(svc.db_path),
    )


@bp.get("/students")
def students():
    svc = service()
    identity: Identity = g.identity
    keyword = request.args.get("q", "").strip()
    class_code = request.args.get("class", "").strip()
    status = request.args.get("status", "").strip()
    element = request.args.get("element", "").strip()

    if identity.is_student:
        own = svc.student_by_no(str(identity.student_no))
        rows = [own] if own is not None else []
    else:
        rows = list(svc.list_students(keyword))
        if class_code:
            rows = [row for row in rows if row["class_code"] == class_code]
        if status:
            rows = [row for row in rows if row["status"] == status]
        if element:
            rows = [row for row in rows if row["primary_element"] == element]

    selected_no = request.args.get("student_no", "")
    selected_index = next(
        (index for index, row in enumerate(rows) if row["student_no"] == selected_no),
        None,
    )
    visible, pagination = _paginate(rows, 12, selected_index)
    if selected_index is not None:
        selected = rows[selected_index]
    elif selected_no:
        selected = None
    else:
        selected = visible[0] if visible else None
    enrollments = (
        svc.enrollments_for_student(selected["student_no"]) if selected is not None else []
    )
    return render_template(
        "students.html",
        students=visible,
        selected=selected,
        enrollments=enrollments,
        pagination=pagination,
        classes=svc.list_classes(),
        families=svc.list_species_families(),
        branches=svc.list_species_branches(),
        drafts=_consume_form_drafts(),
    )


@bp.post("/students/create")
@admin_required
def student_create():
    try:
        student_no = request.form.get("student_no", "").strip()
        svc = service()
        svc.register_student(
            student_no=student_no,
            name=request.form.get("name", "").strip(),
            family=request.form.get("family", ""),
            branch=_optional_form("branch"),
            enrollment_year=_form_int("enrollment_year"),
            class_code=_optional_form("class_code"),
            gender=_optional_form("gender"),
            birth_date=_optional_form("birth_date"),
            age=_form_int("age", optional=True),
            status=request.form.get("status", "在读"),
            primary_element=_optional_form("primary_element"),
            primary_affinity=_optional_form("primary_affinity"),
            contact=_optional_form("contact"),
            dormitory=_optional_form("dormitory"),
            notes=_optional_form("notes"),
        )
        flash("新学生档案已写入名册；初始密码为 123456", "success")
        _clear_form_draft("new-student")
        return redirect(url_for("web.students", student_no=student_no))
    except (ValueError, sqlite3.Error) as error:
        _mutation_error(error)
        _save_form_draft("new-student", error)
        return redirect(url_for("web.students", create=1))


@bp.post("/students/<student_no>/edit")
@admin_required
def student_edit(student_no: str):
    try:
        service().update_student_by_no(
            student_no,
            family=request.form.get("family", ""),
            branch=_optional_form("branch"),
            enrollment_year=_form_int("enrollment_year"),
            class_code=_optional_form("class_code"),
            gender=_optional_form("gender"),
            birth_date=_optional_form("birth_date"),
            age=_form_int("age", optional=True),
            status=request.form.get("status", "在读"),
            primary_element=_optional_form("primary_element"),
            primary_affinity=_optional_form("primary_affinity"),
            contact=_optional_form("contact"),
            dormitory=_optional_form("dormitory"),
            notes=_optional_form("notes"),
        )
        flash("档案修改已保存", "success")
        _clear_form_draft("edit-student")
    except (ValueError, sqlite3.Error) as error:
        _mutation_error(error)
        _save_form_draft("edit-student", error)
        return redirect(url_for("web.students", student_no=student_no, edit=1))
    return redirect(url_for("web.students", student_no=student_no))


@bp.post("/students/<student_no>/delete")
@admin_required
def student_delete(student_no: str):
    try:
        service().delete_student_by_no(student_no)
        flash("学生档案已删除", "success")
        return redirect(url_for("web.students"))
    except (ValueError, sqlite3.Error) as error:
        _mutation_error(error)
        return redirect(url_for("web.students", student_no=student_no))


@bp.post("/students/<student_no>/reset-password")
@admin_required
def student_reset_password(student_no: str):
    try:
        initial = service().reset_student_password(student_no)
        flash(f"密码已重置为 {initial}，学生下次登录需修改密码", "success")
    except (ValueError, sqlite3.Error, OSError) as error:
        _mutation_error(error)
    return redirect(url_for("web.students", student_no=student_no))


@bp.get("/courses")
def courses():
    svc = service()
    identity: Identity = g.identity
    keyword = request.args.get("q", "").strip().lower()
    if identity.is_student:
        enrollments = svc.enrollments_for_student(str(identity.student_no))
        by_code = {row["course_code"]: svc.course_by_code(row["course_code"]) for row in enrollments}
        rows = [row for row in by_code.values() if row is not None]
    else:
        rows = list(svc.list_courses())
    if keyword:
        rows = [
            row for row in rows
            if keyword in f"{row['course_code']} {row['name']} {row['department_name'] or ''}".lower()
        ]
    selected_code = request.args.get("course_code", "")
    selected_index = next(
        (index for index, row in enumerate(rows) if row["course_code"] == selected_code),
        None,
    )
    visible, pagination = _paginate(rows, 9, selected_index)
    if selected_index is not None:
        selected = rows[selected_index]
    elif selected_code:
        selected = None
    else:
        selected = visible[0] if visible else None
    if selected is not None:
        course_enrollments = (
            svc.enrollments_for_course(selected["course_code"])
            if identity.is_admin
            else [
                row for row in svc.enrollments_for_student(str(identity.student_no))
                if row["course_code"] == selected["course_code"]
            ]
        )
    else:
        course_enrollments = []
    return render_template(
        "courses.html",
        courses=visible,
        selected=selected,
        course_enrollments=course_enrollments,
        pagination=pagination,
        departments=svc.list_departments(),
        drafts=_consume_form_drafts(),
    )


@bp.post("/courses/create")
@admin_required
def course_create():
    try:
        code = request.form.get("course_code", "").strip()
        service().create_course(
            course_code=code,
            name=request.form.get("name", "").strip(),
            credits=_form_float("credits"),
            hours=_form_int("hours"),
            department_code=_optional_form("department_code"),
        )
        flash("课程已加入课程矩阵", "success")
        _clear_form_draft("new-course")
        return redirect(url_for("web.courses", course_code=code))
    except (ValueError, sqlite3.Error) as error:
        _mutation_error(error)
        _save_form_draft("new-course", error)
        return redirect(url_for("web.courses", create=1))


@bp.post("/courses/<course_code>/edit")
@admin_required
def course_edit(course_code: str):
    try:
        service().update_course_by_code(
            course_code,
            name=request.form.get("name", "").strip(),
            credits=_form_float("credits"),
            hours=_form_int("hours"),
            department_code=_optional_form("department_code"),
        )
        flash("课程资料已更新", "success")
        _clear_form_draft("edit-course")
    except (ValueError, sqlite3.Error) as error:
        _mutation_error(error)
        _save_form_draft("edit-course", error)
        return redirect(url_for("web.courses", course_code=course_code, edit=1))
    return redirect(url_for("web.courses", course_code=course_code))


@bp.post("/courses/<course_code>/delete")
@admin_required
def course_delete(course_code: str):
    try:
        service().delete_course_by_code(course_code)
        flash("课程及其选课记录已删除", "success")
        return redirect(url_for("web.courses"))
    except (ValueError, sqlite3.Error) as error:
        _mutation_error(error)
        return redirect(url_for("web.courses", course_code=course_code))


@bp.get("/grades")
def grades():
    svc = service()
    identity: Identity = g.identity
    keyword = request.args.get("q", "").strip().lower()
    rows = list(
        svc.list_enrollments()
        if identity.is_admin
        else svc.enrollments_for_student(str(identity.student_no))
    )
    if keyword:
        rows = [
            row for row in rows
            if keyword in f"{row['student_no']} {row['student_name']} {row['course_code']} {row['course_name']}".lower()
        ]
    scores = [float(row["score"]) for row in rows if row["score"] is not None]
    requested_id = request.args.get("id", "")
    try:
        selected_id = int(requested_id or 0)
    except ValueError:
        selected_id = 0
    selected_index = next(
        (index for index, row in enumerate(rows) if row["id"] == selected_id),
        None,
    )
    visible, pagination = _paginate(rows, 14, selected_index)
    if selected_index is not None:
        selected = rows[selected_index]
    elif requested_id:
        selected = None
    else:
        selected = visible[0] if visible else None
    distribution = {
        "90+": len([score for score in scores if score >= 90]),
        "80–89": len([score for score in scores if 80 <= score < 90]),
        "70–79": len([score for score in scores if 70 <= score < 80]),
        "60–69": len([score for score in scores if 60 <= score < 70]),
        "<60": len([score for score in scores if score < 60]),
    }
    return render_template(
        "grades.html",
        grades=visible,
        selected=selected,
        pagination=pagination,
        distribution=distribution,
        average=round(sum(scores) / len(scores), 1) if scores else None,
        highest=max(scores) if scores else None,
        pending=len(rows) - len(scores),
        students=svc.list_students() if identity.is_admin else [],
        course_options=svc.list_courses(),
        drafts=_consume_form_drafts(),
    )


@bp.post("/grades/create")
@admin_required
def grade_create():
    try:
        enrollment_id = service().add_grade(
            student_no=request.form.get("student_no", ""),
            course_code=request.form.get("course_code", ""),
            semester=request.form.get("semester", "").strip(),
            score=_form_float("score", optional=True),
        )
        flash("选课与成绩记录已添加", "success")
        _clear_form_draft("new-grade")
        return redirect(url_for("web.grades", id=enrollment_id))
    except (ValueError, sqlite3.Error) as error:
        _mutation_error(error)
        _save_form_draft("new-grade", error)
        return redirect(url_for("web.grades", create=1))


@bp.post("/grades/<int:enrollment_id>/edit")
@admin_required
def grade_edit(enrollment_id: int):
    try:
        student_no = request.form.get("student_no", "")
        course_code = request.form.get("course_code", "")
        semester = request.form.get("original_semester", "")
        service().update_grade(
            student_no=student_no,
            course_code=course_code,
            semester=semester,
            new_semester=request.form.get("semester", "").strip(),
            score=_form_float("score", optional=True),
        )
        flash("成绩记录已更新", "success")
        _clear_form_draft("edit-grade")
    except (ValueError, sqlite3.Error) as error:
        _mutation_error(error)
        _save_form_draft("edit-grade", error)
        return redirect(url_for("web.grades", id=enrollment_id, edit=1))
    return redirect(url_for("web.grades", id=enrollment_id))


@bp.post("/grades/<int:enrollment_id>/delete")
@admin_required
def grade_delete(enrollment_id: int):
    try:
        service().delete_grade(
            student_no=request.form.get("student_no", ""),
            course_code=request.form.get("course_code", ""),
            semester=request.form.get("semester", ""),
        )
        flash("选课记录已删除", "success")
        return redirect(url_for("web.grades"))
    except (ValueError, sqlite3.Error) as error:
        _mutation_error(error)
        return redirect(url_for("web.grades", id=enrollment_id))


@bp.get("/notices")
def notices():
    svc = service()
    identity: Identity = g.identity
    rows = list(svc.list_announcements(None if identity.is_admin else identity.student_no))
    keyword = request.args.get("q", "").strip().lower()
    if keyword:
        rows = [row for row in rows if keyword in f"{row['title']} {row['body']} {row['class_name']}".lower()]
    requested_id = request.args.get("id", "")
    try:
        selected_id = int(requested_id or 0)
    except ValueError:
        selected_id = 0
    selected_index = next((index for index, row in enumerate(rows) if row["id"] == selected_id), None)
    if selected_index is not None:
        selected = rows[selected_index]
    elif requested_id:
        selected = None
    else:
        selected = rows[0] if rows else None
    return render_template(
        "notices.html",
        notices=rows,
        selected=selected,
        classes=svc.list_classes() if identity.is_admin else [],
        drafts=_consume_form_drafts(),
    )


@bp.post("/notices/create")
@admin_required
def notice_create():
    try:
        notice_id = service().create_announcement(
            title=request.form.get("title", "").strip(),
            body=request.form.get("body", "").strip(),
            class_code=request.form.get("class_code", ""),
        )
        flash("班级公告已发布", "success")
        _clear_form_draft("new-notice")
        return redirect(url_for("web.notices", id=notice_id))
    except (ValueError, sqlite3.Error) as error:
        _mutation_error(error)
        _save_form_draft("new-notice", error)
        return redirect(url_for("web.notices", create=1))


@bp.post("/notices/<int:notice_id>/delete")
@admin_required
def notice_delete(notice_id: int):
    try:
        service().delete_announcement(notice_id)
        flash("公告已删除", "success")
    except (ValueError, sqlite3.Error) as error:
        _mutation_error(error)
    return redirect(url_for("web.notices"))
