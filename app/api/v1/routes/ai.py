"""app/api/v1/routes/ai.py — AI-powered extraction, summarization, and translation endpoints. All sync."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.models.user import User
from app.schemas.common import APIResponse
from app.schemas.upload import (
    ExtractCaseRequest,
    ReportSummaryRequest,
    SummarizeCaseRequest,
    TranslateRequest,
    TranslateResponse,
)

router = APIRouter(prefix="/ai", tags=["AI & NLP"])


@router.post("/extract-case", response_model=APIResponse[dict])
def extract_case(
    request: ExtractCaseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Extract structured case fields from free text using LLM."""
    if not settings.ENABLE_AI_FEATURES:
        raise HTTPException(503, "AI features are disabled on this instance")

    from app.integrations.llm.openai_client import extract_case_from_text
    from app.core.constants import AIInputType
    from app.models.upload import AIExtractionResult

    result = extract_case_from_text(request.text)
    if not result:
        raise HTTPException(503, "AI extraction failed — check OPENAI_API_KEY configuration")

    extraction = AIExtractionResult(
        organization_id=current_user.organization_id,
        input_type=AIInputType.free_text,
        raw_input=request.text[:5000],
        structured_json=result,
        confidence=result.get("confidence"),
        model_used=settings.OPENAI_MODEL,
        prompt_version="v1.2",
    )
    db.add(extraction)
    db.commit()
    db.refresh(extraction)

    return {
        "success": True,
        "data": {
            "extraction_id": str(extraction.id),
            "structured": result,
            "confidence": result.get("confidence"),
        },
    }


@router.post("/summarize-case", response_model=APIResponse[dict])
def summarize_case(
    request: SummarizeCaseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate a brief, plain-language summary of a case."""
    from sqlalchemy import select
    from app.models.case import Case
    from app.integrations.llm.openai_client import summarize_case as ai_summarize

    case = db.execute(
        select(Case).where(
            Case.id == request.case_id,
            Case.organization_id == current_user.organization_id,
        )
    ).scalars().first()
    if not case:
        raise HTTPException(404, "Case not found")

    case_data = {
        "title": case.title,
        "description": case.description,
        "category": case.category.value,
        "urgency": case.urgency_level.value,
        "location": case.location_name,
        "people_affected": case.number_of_people_affected,
        "special_requirements": case.special_requirements,
    }

    summary = ai_summarize(case_data, request.target_language)
    if not summary:
        raise HTTPException(503, "Summarization failed")

    return {"success": True, "data": {"summary": summary, "case_id": str(request.case_id)}}


@router.post("/translate", response_model=APIResponse[TranslateResponse])
def translate_text(
    request: TranslateRequest,
    current_user: User = Depends(get_current_user),
):
    """Translate text to a target language using Google Translate."""
    from app.integrations.translation.google_translate import translate_text as do_translate

    translated, source = do_translate(
        text=request.text,
        target_language=request.target_language,
        source_language=request.source_language,
    )

    result = TranslateResponse(
        original_text=request.text,
        translated_text=translated,
        source_language=source,
        target_language=request.target_language,
    )
    return {"success": True, "data": result}


@router.post("/generate-report-summary", response_model=APIResponse[dict])
def generate_report_summary(
    request: ReportSummaryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate an AI narrative situation report for the organization."""
    from sqlalchemy import func, select
    from app.models.case import Case
    from app.models.volunteer import Volunteer
    from app.integrations.llm.openai_client import generate_report_narrative

    case_count = db.execute(
        select(func.count(Case.id)).where(Case.organization_id == current_user.organization_id)
    ).scalar()
    vol_count = db.execute(
        select(func.count(Volunteer.id)).where(
            Volunteer.organization_id == current_user.organization_id
        )
    ).scalar()

    stats = {
        "total_cases": case_count,
        "total_volunteers": vol_count,
        "period": request.period,
        "disaster_filter": request.disaster_type,
    }

    narrative = generate_report_narrative(stats, request.period)
    if not narrative:
        raise HTTPException(503, "Report generation failed")

    return {"success": True, "data": {"narrative": narrative, "stats": stats}}
