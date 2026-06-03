import os, shutil, uuid, pathlib, mimetypes
from fastapi import FastAPI, Request, Depends, Form, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .models import Base, engine, get_db, User, Section, Page, Attachment, slugify
from .auth import hash_password, verify_password, create_token, get_user
from .seed import seed

# ── Bootstrap ─────────────────────────────────────────
Base.metadata.create_all(bind=engine)

app = FastAPI(docs_url=None, redoc_url=None)

BASE_DIR    = pathlib.Path(__file__).parent.parent
UPLOAD_DIR  = pathlib.Path("/app/uploads")
STATIC_DIR  = BASE_DIR / "static"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
STATIC_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")
app.mount("/static",  StaticFiles(directory=str(STATIC_DIR)), name="static")

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@app.on_event("startup")
def startup():
    db = next(get_db())
    try:
        seed(db)
    finally:
        db.close()


# ═══════════════════════════════════════════════════════
#  PORTAL — público, sem login
# ═══════════════════════════════════════════════════════

@app.get("/", response_class=HTMLResponse)
def home(request: Request, db: Session = Depends(get_db)):
    sections = db.query(Section).filter_by(active=True).order_by(Section.order).all()
    return templates.TemplateResponse("portal/home.html",
        {"request": request, "sections": sections, "user": get_user(request)})


@app.get("/s/{slug}", response_class=HTMLResponse)
def portal_section(slug: str, request: Request, db: Session = Depends(get_db)):
    section = db.query(Section).filter_by(slug=slug, active=True).first()
    if not section:
        raise HTTPException(404)
    sections = db.query(Section).filter_by(active=True).order_by(Section.order).all()
    pages = [p for p in section.pages if p.active]
    return templates.TemplateResponse("portal/section.html",
        {"request": request, "section": section, "pages": pages,
         "sections": sections, "user": get_user(request),
         "cur_section": section, "cur_page": None})


@app.get("/p/{page_id}", response_class=HTMLResponse)
def portal_page(page_id: int, request: Request, db: Session = Depends(get_db)):
    page = db.query(Page).filter_by(id=page_id, active=True).first()
    if not page:
        raise HTTPException(404)
    section = page.section
    sections = db.query(Section).filter_by(active=True).order_by(Section.order).all()
    return templates.TemplateResponse("portal/page.html",
        {"request": request, "page": page, "section": section,
         "sections": sections, "user": get_user(request),
         "cur_section": section, "cur_page": page})


@app.get("/download/{attach_id}")
def download_file(attach_id: int, db: Session = Depends(get_db)):
    att = db.query(Attachment).get(attach_id)
    if not att:
        raise HTTPException(404)
    path = UPLOAD_DIR / att.stored_as
    if not path.exists():
        raise HTTPException(404)
    return FileResponse(str(path), filename=att.filename,
                        media_type=att.mime_type or "application/octet-stream")


# ═══════════════════════════════════════════════════════
#  ADMIN — login
# ═══════════════════════════════════════════════════════

@app.get("/admin", response_class=HTMLResponse)
@app.get("/admin/", response_class=HTMLResponse)
def admin_root(request: Request):
    u = get_user(request)
    return RedirectResponse("/admin/dashboard" if u else "/admin/login")


@app.get("/admin/login", response_class=HTMLResponse)
def admin_login_get(request: Request):
    if get_user(request):
        return RedirectResponse("/admin/dashboard")
    return templates.TemplateResponse("admin/login.html",
        {"request": request, "error": ""})


@app.post("/admin/login")
def admin_login_post(request: Request,
                     username: str = Form(...), password: str = Form(...),
                     db: Session = Depends(get_db)):
    u = db.query(User).filter_by(username=username, active=True).first()
    if not u or not verify_password(password, u.password):
        return templates.TemplateResponse("admin/login.html",
            {"request": request, "error": "Usuário ou senha incorretos."})
    token = create_token({"sub": str(u.id), "username": u.username,
                          "role": u.role, "name": u.name})
    resp = RedirectResponse("/admin/dashboard", status_code=303)
    resp.set_cookie("medsel_token", token, httponly=True,
                    samesite="lax", max_age=3600 * 10)
    return resp


@app.get("/admin/logout")
def admin_logout():
    resp = RedirectResponse("/admin/login", status_code=303)
    resp.delete_cookie("medsel_token")
    return resp


# ── helpers ──
def _check(request, need_admin=False):
    u = get_user(request)
    if not u:
        return None, RedirectResponse("/admin/login")
    if need_admin and u["role"] != "admin":
        return None, RedirectResponse("/admin/dashboard")
    if u["role"] not in ("admin", "editor"):
        return None, RedirectResponse("/admin/login")
    return u, None


# ═══════════════════════════════════════════════════════
#  ADMIN — dashboard
# ═══════════════════════════════════════════════════════

@app.get("/admin/dashboard", response_class=HTMLResponse)
def admin_dashboard(request: Request, db: Session = Depends(get_db)):
    u = get_user(request)
    if not u or u["role"] not in ("admin", "editor"):
        return RedirectResponse("/admin/login")
    sections = db.query(Section).order_by(Section.order).all()
    total_pages = db.query(Page).count()
    total_files = db.query(Attachment).count()
    return templates.TemplateResponse("admin/dashboard.html",
        {"request": request, "user": u, "sections": sections,
         "total_pages": total_pages, "total_files": total_files,
         "active": "dashboard"})


# ═══════════════════════════════════════════════════════
#  ADMIN — seções
# ═══════════════════════════════════════════════════════

@app.get("/admin/sections", response_class=HTMLResponse)
def adm_sections(request: Request, db: Session = Depends(get_db)):
    u, redir = _check(request)
    if redir: return redir
    sections = db.query(Section).order_by(Section.order).all()
    return templates.TemplateResponse("admin/sections.html",
        {"request": request, "user": u, "sections": sections, "active": "sections"})


@app.get("/admin/sections/new", response_class=HTMLResponse)
def adm_section_new_get(request: Request):
    u, redir = _check(request)
    if redir: return redir
    return templates.TemplateResponse("admin/section_form.html",
        {"request": request, "user": u, "sec": None, "error": "", "active": "sections"})


@app.post("/admin/sections/new")
def adm_section_new_post(request: Request,
    name: str = Form(...), icon: str = Form("📁"),
    color: str = Form("#2563a8"), order: int = Form(99),
    db: Session = Depends(get_db)):
    u, redir = _check(request)
    if redir: return redir
    slug = slugify(name)
    if db.query(Section).filter_by(slug=slug).first():
        slug = f"{slug}-{uuid.uuid4().hex[:4]}"
    db.add(Section(slug=slug, name=name, icon=icon, color=color, order=order))
    db.commit()
    return RedirectResponse("/admin/sections", status_code=303)


@app.get("/admin/sections/{sid}/edit", response_class=HTMLResponse)
def adm_section_edit_get(sid: int, request: Request, db: Session = Depends(get_db)):
    u, redir = _check(request)
    if redir: return redir
    sec = db.query(Section).get(sid)
    if not sec: raise HTTPException(404)
    return templates.TemplateResponse("admin/section_form.html",
        {"request": request, "user": u, "sec": sec, "error": "", "active": "sections"})


@app.post("/admin/sections/{sid}/edit")
def adm_section_edit_post(sid: int, request: Request,
    name: str = Form(...), icon: str = Form("📁"),
    color: str = Form("#2563a8"), order: int = Form(99),
    active: str = Form("on"), db: Session = Depends(get_db)):
    u, redir = _check(request)
    if redir: return redir
    sec = db.query(Section).get(sid)
    if not sec: raise HTTPException(404)
    sec.name = name; sec.icon = icon
    sec.color = color; sec.order = order
    sec.active = (active == "on")
    db.commit()
    return RedirectResponse("/admin/sections", status_code=303)


@app.post("/admin/sections/{sid}/delete")
def adm_section_delete(sid: int, request: Request, db: Session = Depends(get_db)):
    u, redir = _check(request, need_admin=True)
    if redir: return redir
    sec = db.query(Section).get(sid)
    if sec:
        db.delete(sec); db.commit()
    return RedirectResponse("/admin/sections", status_code=303)


# ═══════════════════════════════════════════════════════
#  ADMIN — páginas (editor rico)
# ═══════════════════════════════════════════════════════

@app.get("/admin/pages", response_class=HTMLResponse)
def adm_pages(request: Request, section_id: int = None,
              db: Session = Depends(get_db)):
    u, redir = _check(request)
    if redir: return redir
    q = db.query(Page)
    if section_id:
        q = q.filter_by(section_id=section_id)
    pages = q.order_by(Page.section_id, Page.order).all()
    sections = db.query(Section).order_by(Section.order).all()
    cur = db.query(Section).get(section_id) if section_id else None
    return templates.TemplateResponse("admin/pages.html",
        {"request": request, "user": u, "pages": pages,
         "sections": sections, "cur_section": cur, "active": "pages"})


@app.get("/admin/pages/new", response_class=HTMLResponse)
def adm_page_new_get(request: Request, section_id: int = None,
                     db: Session = Depends(get_db)):
    u, redir = _check(request)
    if redir: return redir
    sections = db.query(Section).order_by(Section.order).all()
    return templates.TemplateResponse("admin/page_editor.html",
        {"request": request, "user": u, "page": None, "sections": sections,
         "preselect": section_id, "error": "", "active": "pages"})


@app.post("/admin/pages/new")
async def adm_page_new_post(request: Request,
    section_id: int = Form(...), title: str = Form(...),
    content: str = Form(""), order: int = Form(99),
    files: list[UploadFile] = File(default=[]),
    db: Session = Depends(get_db)):
    u, redir = _check(request)
    if redir: return redir
    slug = slugify(title)
    existing = db.query(Page).filter_by(section_id=section_id, slug=slug).first()
    if existing:
        slug = f"{slug}-{uuid.uuid4().hex[:4]}"
    page = Page(section_id=section_id, title=title,
                slug=slug, content=content, order=order)
    db.add(page); db.flush()
    await _save_attachments(files, page.id, db)
    db.commit()
    return RedirectResponse(f"/admin/pages?section_id={section_id}", status_code=303)


@app.get("/admin/pages/{pid}/edit", response_class=HTMLResponse)
def adm_page_edit_get(pid: int, request: Request, db: Session = Depends(get_db)):
    u, redir = _check(request)
    if redir: return redir
    page = db.query(Page).get(pid)
    if not page: raise HTTPException(404)
    sections = db.query(Section).order_by(Section.order).all()
    return templates.TemplateResponse("admin/page_editor.html",
        {"request": request, "user": u, "page": page, "sections": sections,
         "preselect": page.section_id, "error": "", "active": "pages"})


@app.post("/admin/pages/{pid}/edit")
async def adm_page_edit_post(pid: int, request: Request,
    section_id: int = Form(...), title: str = Form(...),
    content: str = Form(""), order: int = Form(99),
    active: str = Form("on"),
    files: list[UploadFile] = File(default=[]),
    db: Session = Depends(get_db)):
    u, redir = _check(request)
    if redir: return redir
    page = db.query(Page).get(pid)
    if not page: raise HTTPException(404)
    page.section_id = section_id; page.title = title
    page.content = content; page.order = order
    page.active = (active == "on")
    await _save_attachments(files, pid, db)
    db.commit()
    return RedirectResponse(f"/admin/pages?section_id={section_id}", status_code=303)


@app.post("/admin/pages/{pid}/delete")
def adm_page_delete(pid: int, request: Request, db: Session = Depends(get_db)):
    u, redir = _check(request)
    if redir: return redir
    page = db.query(Page).get(pid)
    if page:
        sid = page.section_id
        db.delete(page); db.commit()
        return RedirectResponse(f"/admin/pages?section_id={sid}", status_code=303)
    return RedirectResponse("/admin/pages", status_code=303)


@app.post("/admin/attachments/{aid}/delete")
def adm_attach_delete(aid: int, request: Request,
                      next_url: str = Form("/admin/pages"),
                      db: Session = Depends(get_db)):
    u, redir = _check(request)
    if redir: return redir
    att = db.query(Attachment).get(aid)
    if att:
        f = UPLOAD_DIR / att.stored_as
        if f.exists(): f.unlink()
        db.delete(att); db.commit()
    return RedirectResponse(next_url, status_code=303)


async def _save_attachments(files, page_id, db):
    for f in files:
        if not f.filename:
            continue
        ext = pathlib.Path(f.filename).suffix
        stored = f"{uuid.uuid4().hex}{ext}"
        dest = UPLOAD_DIR / stored
        with open(dest, "wb") as out:
            shutil.copyfileobj(f.file, out)
        size = dest.stat().st_size
        mime = f.content_type or mimetypes.guess_type(f.filename)[0] or "application/octet-stream"
        db.add(Attachment(page_id=page_id, filename=f.filename,
                          stored_as=stored, mime_type=mime, size_bytes=size))


# ═══════════════════════════════════════════════════════
#  ADMIN — upload de imagem inline (para o editor)
# ═══════════════════════════════════════════════════════

@app.post("/admin/upload-image")
async def upload_image(request: Request,
                       image: UploadFile = File(...)):
    u = get_user(request)
    if not u or u["role"] not in ("admin", "editor"):
        raise HTTPException(403)
    ext = pathlib.Path(image.filename).suffix.lower()
    if ext not in (".jpg", ".jpeg", ".png", ".gif", ".webp"):
        raise HTTPException(400, "Tipo não permitido")
    stored = f"{uuid.uuid4().hex}{ext}"
    dest = UPLOAD_DIR / stored
    with open(dest, "wb") as out:
        shutil.copyfileobj(image.file, out)
    return {"url": f"/uploads/{stored}"}


# ═══════════════════════════════════════════════════════
#  ADMIN — usuários
# ═══════════════════════════════════════════════════════

@app.get("/admin/users", response_class=HTMLResponse)
def adm_users(request: Request, db: Session = Depends(get_db)):
    u, redir = _check(request, need_admin=True)
    if redir: return redir
    users = db.query(User).order_by(User.id).all()
    return templates.TemplateResponse("admin/users.html",
        {"request": request, "user": u, "users": users, "active": "users"})


@app.get("/admin/users/new", response_class=HTMLResponse)
def adm_user_new_get(request: Request):
    u, redir = _check(request, need_admin=True)
    if redir: return redir
    return templates.TemplateResponse("admin/user_form.html",
        {"request": request, "user": u, "editing": None, "error": "", "active": "users"})


@app.post("/admin/users/new")
def adm_user_new_post(request: Request,
    username: str = Form(...), name: str = Form(...),
    password: str = Form(...), role: str = Form("viewer"),
    db: Session = Depends(get_db)):
    u, redir = _check(request, need_admin=True)
    if redir: return redir
    if db.query(User).filter_by(username=username).first():
        return templates.TemplateResponse("admin/user_form.html",
            {"request": request, "user": u, "editing": None,
             "error": "Usuário já existe.", "active": "users"})
    db.add(User(username=username, name=name,
                password=hash_password(password), role=role))
    db.commit()
    return RedirectResponse("/admin/users", status_code=303)


@app.get("/admin/users/{uid}/edit", response_class=HTMLResponse)
def adm_user_edit_get(uid: int, request: Request, db: Session = Depends(get_db)):
    u, redir = _check(request, need_admin=True)
    if redir: return redir
    editing = db.query(User).get(uid)
    if not editing: raise HTTPException(404)
    return templates.TemplateResponse("admin/user_form.html",
        {"request": request, "user": u, "editing": editing,
         "error": "", "active": "users"})


@app.post("/admin/users/{uid}/edit")
def adm_user_edit_post(uid: int, request: Request,
    username: str = Form(...), name: str = Form(...),
    password: str = Form(""), role: str = Form("viewer"),
    active: str = Form("on"), db: Session = Depends(get_db)):
    u, redir = _check(request, need_admin=True)
    if redir: return redir
    editing = db.query(User).get(uid)
    if not editing: raise HTTPException(404)
    editing.username = username; editing.name = name
    editing.role = role; editing.active = (active == "on")
    if password:
        editing.password = hash_password(password)
    db.commit()
    return RedirectResponse("/admin/users", status_code=303)


@app.post("/admin/users/{uid}/delete")
def adm_user_delete(uid: int, request: Request, db: Session = Depends(get_db)):
    u, redir = _check(request, need_admin=True)
    if redir: return redir
    if int(u["sub"]) == uid:
        return RedirectResponse("/admin/users", status_code=303)
    editing = db.query(User).get(uid)
    if editing:
        db.delete(editing); db.commit()
    return RedirectResponse("/admin/users", status_code=303)
