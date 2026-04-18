import json
import asyncio
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config import DB_PATH, UPLOAD_DIR, OUTPUT_DIR, HOST, PORT
from models import Base, Project, UploadedFile, Slide, Comment, ProjectStatus

# Database setup
engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

app = FastAPI(title="DynaBridge Brand Discovery", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Project CRUD ─────────────────────────────────────────────

@app.get("/api/projects")
def list_projects():
    with Session() as db:
        projects = db.query(Project).order_by(Project.created_at.desc()).all()
        return [_project_dict(p) for p in projects]


@app.post("/api/projects")
def create_project(
    name: str = Form(...),
    brand_url: str = Form(""),
    competitor_urls: str = Form("[]"),
    language: str = Form("en"),
    phase: str = Form("brand_reality"),
):
    with Session() as db:
        project = Project(
            name=name,
            brand_url=brand_url,
            competitor_urls=competitor_urls,
            language=language,
            phase=phase,
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        return _project_dict(project)


@app.get("/api/projects/{project_id}")
def get_project(project_id: int):
    with Session() as db:
        project = db.query(Project).get(project_id)
        if not project:
            raise HTTPException(404, "Project not found")
        return _project_dict(project, include_slides=True, include_comments=True)


@app.patch("/api/projects/{project_id}")
def update_project(
    project_id: int,
    name: str = Form(None),
    brand_url: str = Form(None),
    competitor_urls: str = Form(None),
    language: str = Form(None),
    phase: str = Form(None),
):
    with Session() as db:
        project = db.query(Project).get(project_id)
        if not project:
            raise HTTPException(404, "Project not found")
        if name is not None:
            project.name = name
        if brand_url is not None:
            project.brand_url = brand_url
        if competitor_urls is not None:
            project.competitor_urls = competitor_urls
        if language is not None:
            project.language = language
        if phase is not None:
            project.phase = phase
        db.commit()
        db.refresh(project)
        return _project_dict(project)


@app.delete("/api/projects/{project_id}")
def delete_project(project_id: int):
    with Session() as db:
        project = db.query(Project).get(project_id)
        if not project:
            raise HTTPException(404, "Project not found")
        db.query(Comment).filter_by(project_id=project_id).delete()
        db.query(Slide).filter_by(project_id=project_id).delete()
        db.query(UploadedFile).filter_by(project_id=project_id).delete()
        db.delete(project)
        db.commit()
        return {"deleted": True}


# ─── File Upload ──────────────────────────────────────────────

@app.post("/api/projects/{project_id}/files")
async def upload_file(project_id: int, file: UploadFile = File(...)):
    project_dir = UPLOAD_DIR / str(project_id)
    project_dir.mkdir(exist_ok=True)

    file_path = project_dir / file.filename
    content = await file.read()
    file_path.write_bytes(content)

    suffix = Path(file.filename).suffix.lower().lstrip(".")
    file_type = {"pdf": "pdf", "docx": "docx", "doc": "docx",
                 "pptx": "pptx", "png": "image", "jpg": "image",
                 "jpeg": "image"}.get(suffix, "other")

    with Session() as db:
        uploaded = UploadedFile(
            project_id=project_id,
            filename=file.filename,
            file_path=str(file_path),
            file_type=file_type,
        )
        db.add(uploaded)
        db.commit()
        return {"id": uploaded.id, "filename": file.filename, "type": file_type}


# ─── Generate Pipeline ───────────────────────────────────────

@app.post("/api/projects/{project_id}/generate")
async def generate_report(project_id: int, phase: str = Form("full")):
    """Trigger the full generation pipeline. Returns SSE stream of progress.

    Args:
        phase: "brand_reality" | "market_structure" | "full"
    """

    async def event_stream():
        with Session() as db:
            project = db.query(Project).get(project_id)
            if not project:
                yield _sse("error", {"message": "Project not found"})
                return

            # Save the phase to the project
            project.phase = phase

            # Step 1: Scrape website
            yield _sse("progress", {"step": "scraping", "message": "Crawling brand website..."})
            project.status = ProjectStatus.SCRAPING
            db.commit()

            from pipeline.scraper import scrape_brand_website
            scrape_result = await scrape_brand_website(project.brand_url)
            yield _sse("progress", {"step": "scraping", "message": "Website crawled", "done": True})

            # Step 2: Parse uploaded documents
            yield _sse("progress", {"step": "parsing", "message": "Parsing uploaded documents..."})
            project.status = ProjectStatus.PARSING
            db.commit()

            files = db.query(UploadedFile).filter_by(project_id=project_id).all()
            from pipeline.doc_parser import parse_documents
            parsed_docs = await parse_documents([f.file_path for f in files])
            yield _sse("progress", {"step": "parsing", "message": "Documents parsed", "done": True})

            # Step 2b: E-commerce scraping
            ecommerce_data = None
            review_data = None
            try:
                yield _sse("progress", {"step": "ecommerce", "message": "Scraping e-commerce data..."})
                from pipeline.ecommerce_scraper import scrape_ecommerce
                ecommerce_data = await scrape_ecommerce(project.name)
                yield _sse("progress", {"step": "ecommerce", "message": "E-commerce data collected", "done": True})
            except Exception:
                yield _sse("progress", {"step": "ecommerce", "message": "E-commerce scraping skipped", "done": True})

            # Step 2c: Review collection
            try:
                yield _sse("progress", {"step": "reviews", "message": "Collecting customer reviews..."})
                from pipeline.review_collector import collect_reviews
                review_data = await collect_reviews(project.name)
                yield _sse("progress", {"step": "reviews", "message": "Reviews collected", "done": True})
            except Exception:
                yield _sse("progress", {"step": "reviews", "message": "Review collection skipped", "done": True})

            # Step 2d: Auto competitor discovery (uses Managed Agent with web_search when available)
            competitor_data = None
            manual_competitors = json.loads(project.competitor_urls) if project.competitor_urls else []
            try:
                yield _sse("progress", {"step": "competitors", "message": "Discovering competitors (AI agent research)..."})
                from pipeline.competitor_discovery import discover_competitors
                discovered = await discover_competitors(
                    brand_name=project.name,
                    brand_url=project.brand_url,
                    scrape_data=scrape_result,
                    ecommerce_data=ecommerce_data,
                    max_competitors=8,
                )
                competitor_data = discovered

                # Merge manual + discovered names (dedup)
                discovered_names = [c["name"] for c in discovered]
                all_competitor_names = list(manual_competitors)
                for name in discovered_names:
                    if name.lower() not in [m.lower() for m in all_competitor_names]:
                        all_competitor_names.append(name)

                # Save merged list back to project
                project.competitor_urls = json.dumps(all_competitor_names, ensure_ascii=False)
                db.commit()

                yield _sse("progress", {
                    "step": "competitors",
                    "message": f"Found {len(discovered)} competitors",
                    "done": True,
                    "competitors": discovered,
                })
            except Exception:
                yield _sse("progress", {"step": "competitors", "message": "Competitor discovery skipped", "done": True})

            # Step 2e: Desktop research pipeline (3 sequential sessions)
            desktop_research = None
            industry_data = None
            try:
                # Session 1: Brand + Category Research
                yield _sse("progress", {"step": "researching", "message": "Researching brand background and category..."})
                from pipeline.managed_agent import research_brand_context
                brand_context = await research_brand_context(
                    brand_name=project.name,
                    brand_url=project.brand_url,
                )
                yield _sse("progress", {"step": "researching", "message": "Brand research complete. Cooling down before next session..."})
                await asyncio.sleep(30)

                # Re-discover competitors using brand context if initial discovery was poor
                comp_names = json.loads(project.competitor_urls) if project.competitor_urls else []

                def _is_bad_competitor_name(n):
                    n_lower = n.lower()
                    if len(n) > 40 or n.startswith("(") or n.startswith("$"):
                        return True
                    if any(kw in n_lower for kw in ["amazon", "buying", "reviewed", "past month", "/count", "stainless", "recycled", "contains"]):
                        return True
                    if "$" in n or n_lower in ("other", "none", "n/a"):
                        return True
                    return False

                bad_names = [n for n in comp_names if _is_bad_competitor_name(n)]
                if len(bad_names) >= len(comp_names) / 2 or not comp_names:
                    yield _sse("progress", {"step": "researching", "message": "Re-discovering competitors with category context..."})
                    cat_name = ""
                    if brand_context and brand_context.get("category_landscape"):
                        cat_name = brand_context["category_landscape"].get("category_name", "")
                    from pipeline.managed_agent import discover_competitors_managed
                    rediscovered = await discover_competitors_managed(
                        brand_name=project.name,
                        brand_url=project.brand_url,
                        category_context=cat_name,
                        max_competitors=8,
                    )
                    if rediscovered and len(rediscovered) >= 3:
                        comp_names = [c["name"] for c in rediscovered]
                        project.competitor_urls = json.dumps(comp_names, ensure_ascii=False)
                        db.commit()
                        yield _sse("progress", {"step": "researching", "message": f"Re-discovered {len(comp_names)} competitors"})
                        await asyncio.sleep(30)

                # Session 2: Competitor Deep Profiles
                competitor_profiles = []
                if comp_names:
                    yield _sse("progress", {"step": "researching", "message": f"Deep-researching {len(comp_names)} competitors..."})
                    from pipeline.managed_agent import research_competitor_profiles
                    competitor_profiles = await research_competitor_profiles(
                        brand_name=project.name,
                        competitors=comp_names,
                        category="",
                        brand_context=brand_context,
                    )
                    yield _sse("progress", {"step": "researching", "message": f"Competitor profiles complete ({len(competitor_profiles)} profiled). Cooling down..."})
                    await asyncio.sleep(30)

                # Session 3: Consumer + Market Research
                yield _sse("progress", {"step": "researching", "message": "Researching consumer behavior and market dynamics..."})
                from pipeline.managed_agent import research_consumer_landscape
                consumer_landscape = await research_consumer_landscape(
                    brand_name=project.name,
                    category="",
                    brand_context=brand_context,
                    competitor_profiles=competitor_profiles,
                )
                yield _sse("progress", {"step": "researching", "message": "Consumer research complete"})

                desktop_research = {
                    "brand_context": brand_context,
                    "competitor_profiles": competitor_profiles,
                    "consumer_landscape": consumer_landscape,
                }

                # Extract industry data from brand_context for backward compatibility
                if brand_context and brand_context.get("category_landscape"):
                    industry_data = brand_context["category_landscape"]

            except Exception as e:
                yield _sse("progress", {"step": "researching", "message": f"Desktop research partially complete: {str(e)[:100]}"})

            # Step 3: AI Analysis
            yield _sse("progress", {"step": "analyzing", "message": "Running AI brand analysis..."})
            project.status = ProjectStatus.ANALYZING
            db.commit()

            try:
                from pipeline.analyzer import analyze_brand
                competitors = json.loads(project.competitor_urls) if project.competitor_urls else []
                analysis = await analyze_brand(
                    brand_name=project.name,
                    brand_url=project.brand_url,
                    scrape_data=scrape_result,
                    document_data=parsed_docs,
                    competitors=competitors,
                    language=project.language,
                    phase=phase,
                    ecommerce_data=ecommerce_data,
                    review_data=review_data,
                    competitor_data=competitor_data,
                    desktop_research=desktop_research,
                )
                if industry_data:
                    analysis["industry_trends"] = industry_data
                project.analysis_json = json.dumps(analysis, ensure_ascii=False)
                db.commit()
                yield _sse("progress", {"step": "analyzing", "message": "Analysis complete", "done": True})
            except Exception as e:
                import traceback
                traceback.print_exc()
                project.status = ProjectStatus.DRAFT
                db.commit()
                yield _sse("error", {"message": f"AI analysis failed: {str(e)}"})
                return

            # Step 3b: Collect images for PPT (with category-aware keywords)
            collected_images = None
            try:
                yield _sse("progress", {"step": "images", "message": "Collecting brand images..."})
                from pipeline.image_collector import collect_images, infer_category_keywords
                cat_keywords = infer_category_keywords(
                    brand_name=project.name,
                    category="",
                    brand_context=desktop_research.get("brand_context") if desktop_research else None,
                )
                collected_images = await collect_images(
                    project_id=project_id,
                    brand_name=project.name,
                    brand_url=project.brand_url,
                    scrape_data=scrape_result,
                    ecommerce_data=ecommerce_data,
                    category_keywords=cat_keywords,
                )
                img_count = len(collected_images.get("all", []))
                yield _sse("progress", {"step": "images", "message": f"Collected {img_count} images", "done": True})
            except Exception:
                yield _sse("progress", {"step": "images", "message": "Image collection skipped", "done": True})

            # Step 4: Generate PPT
            yield _sse("progress", {"step": "generating", "message": "Generating PowerPoint..."})
            project.status = ProjectStatus.GENERATING
            db.commit()

            try:
                from pipeline.ppt_generator import generate_pptx
                pptx_path, slide_previews = await generate_pptx(
                    project_id=project_id,
                    analysis=analysis,
                    brand_name=project.name,
                    phase=phase,
                    collected_images=collected_images,
                )
                project.pptx_path = str(pptx_path)
                project.status = ProjectStatus.REVIEW
                db.commit()

                # Delete old slide records before saving new ones
                db.query(Slide).filter_by(project_id=project_id).delete()
                db.commit()

                # Save slide records
                for i, preview in enumerate(slide_previews):
                    slide = Slide(
                        project_id=project_id,
                        order=i,
                        slide_type=preview.get("type", "unknown"),
                        content_json=json.dumps(preview.get("content", {}), ensure_ascii=False),
                        preview_path=preview.get("preview_path", ""),
                    )
                    db.add(slide)
                db.commit()

                yield _sse("progress", {"step": "generating", "message": "PowerPoint generated", "done": True})
                yield _sse("complete", {"pptx_path": str(pptx_path), "slide_count": len(slide_previews)})
            except Exception as e:
                project.status = ProjectStatus.DRAFT
                db.commit()
                yield _sse("error", {"message": f"PPT generation failed: {str(e)}"})

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# ─── Slide Previews ──────────────────────────────────────────

@app.get("/api/projects/{project_id}/slides")
def get_slides(project_id: int):
    with Session() as db:
        slides = db.query(Slide).filter_by(project_id=project_id).order_by(Slide.order).all()
        return [{"order": s.order, "type": s.slide_type,
                 "content": json.loads(s.content_json),
                 "preview_url": f"/api/slides/{s.id}/preview"} for s in slides]


@app.get("/api/slides/{slide_id}/preview")
def get_slide_preview(slide_id: int):
    with Session() as db:
        slide = db.query(Slide).get(slide_id)
        if not slide or not slide.preview_path:
            raise HTTPException(404, "Preview not found")
        return FileResponse(slide.preview_path, media_type="image/png")


# ─── Comments / Review ───────────────────────────────────────

@app.post("/api/projects/{project_id}/comments")
def add_comment(
    project_id: int,
    slide_order: Optional[int] = Form(None),
    author: str = Form(...),
    content: str = Form(...),
):
    with Session() as db:
        comment = Comment(
            project_id=project_id,
            slide_order=slide_order,
            author=author,
            content=content,
        )
        db.add(comment)
        db.commit()
        return {"id": comment.id, "author": author, "content": content}


@app.get("/api/projects/{project_id}/comments")
def get_comments(project_id: int):
    with Session() as db:
        comments = db.query(Comment).filter_by(project_id=project_id).order_by(Comment.created_at).all()
        return [{"id": c.id, "slide_order": c.slide_order, "author": c.author,
                 "content": c.content, "resolved": bool(c.resolved),
                 "created_at": c.created_at.isoformat()} for c in comments]


@app.patch("/api/comments/{comment_id}/resolve")
def resolve_comment(comment_id: int):
    with Session() as db:
        comment = db.query(Comment).get(comment_id)
        if not comment:
            raise HTTPException(404)
        comment.resolved = 1
        db.commit()
        return {"resolved": True}


# ─── Survey Design ──────────────────────────────────────────

@app.post("/api/projects/{project_id}/survey")
async def design_survey_endpoint(project_id: int):
    """Generate a customized survey questionnaire for a project."""
    with Session() as db:
        project = db.query(Project).get(project_id)
        if not project:
            raise HTTPException(404, "Project not found")

        from pipeline.survey_designer import design_survey
        competitors = json.loads(project.competitor_urls) if project.competitor_urls else []

        context = ""
        if project.analysis_json:
            try:
                analysis = json.loads(project.analysis_json)
                cap = analysis.get("capabilities", {})
                comp = analysis.get("competition", {})
                context = f"Capabilities summary: {cap.get('capabilities_summary', '')}\n"
                context += f"Competition summary: {comp.get('competition_summary', '')}"
            except (json.JSONDecodeError, KeyError):
                pass

        survey = await design_survey(
            brand_name=project.name,
            brand_url=project.brand_url,
            competitors=competitors,
            language=project.language,
            analysis_context=context,
        )
        return survey


# ─── Download ─────────────────────────────────────────────────

@app.get("/api/projects/{project_id}/download")
def download_pptx(project_id: int):
    with Session() as db:
        project = db.query(Project).get(project_id)
        if not project or not project.pptx_path:
            raise HTTPException(404, "PPTX not ready")
        return FileResponse(
            project.pptx_path,
            media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            filename=f"{project.name}_Brand_Discovery.pptx",
        )


# ─── Helpers ──────────────────────────────────────────────────

def _project_dict(p: Project, include_slides=False, include_comments=False):
    d = {
        "id": p.id, "name": p.name, "brand_url": p.brand_url,
        "competitor_urls": json.loads(p.competitor_urls) if p.competitor_urls else [],
        "status": p.status, "language": p.language,
        "phase": getattr(p, "phase", None) or "brand_reality",
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
        "has_pptx": bool(p.pptx_path),
        "slide_count": len(p.slides) if p.slides else 0,
        "file_count": len(p.files) if p.files else 0,
        "comment_count": len(p.comments) if p.comments else 0,
    }
    if include_slides:
        d["slides"] = [{"order": s.order, "type": s.slide_type,
                        "preview_url": f"/api/slides/{s.id}/preview"} for s in p.slides]
    if include_comments:
        d["comments"] = [{"id": c.id, "slide_order": c.slide_order, "author": c.author,
                          "content": c.content, "resolved": bool(c.resolved)} for c in p.comments]
    return d


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT)
