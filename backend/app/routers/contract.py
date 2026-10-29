import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, status, Path, Body
from app.services.vector_store import vector_store
from app.services.contract_analyzer import ContractAnalyzerService
from app.schemas.contract import (
    ContractAnalysisRequest,
    ContractAnalysisResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["Contract Intelligence"])

_contract_analyzer = ContractAnalyzerService(vector_store=vector_store)


@router.get("/contract/categories", response_model=List[str])
async def get_contract_categories():
    """
    List all 41 standard CUAD clause categories supported by the experimental trigger baseline.
    """
    return _contract_analyzer.get_supported_categories()


@router.post("/{doc_id}/contract-analysis", response_model=ContractAnalysisResponse)
async def analyze_document_contract(
    doc_id: str = Path(..., min_length=1, description="Identifier of the already-uploaded document to analyze"),
    request: Optional[ContractAnalysisRequest] = Body(default_factory=ContractAnalysisRequest),
):
    """
    Analyze an explicitly selected uploaded document for 41 CUAD legal clause categories.

    - **Academic Demonstration Only**: Uses the CUAD lexical trigger baseline extractor.
      Does NOT invoke transformers, fine-tuned checkpoints, or external APIs.
    - **Explicit Document Selection**: Operates exclusively on the selected `doc_id`.
      Does not automatically classify or analyze every uploaded file.
    - **Distinction of Absence**: Categories where no pattern is found above the threshold
      are explicitly marked as 'not detected by experimental extractor', NOT as verified absence.
    - **Source Provenance**: Every detected clause includes verbatim text, source page number,
      and exact character offsets within the page text.
    """
    clean_doc_id = doc_id.strip()
    if not clean_doc_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document ID cannot be empty or contain only whitespace.",
        )

    req = request or ContractAnalysisRequest()

    try:
        response = _contract_analyzer.analyze_document(
            doc_id=clean_doc_id,
            confidence_threshold=req.confidence_threshold,
            categories=req.categories,
        )
        return response
    except ValueError as exc:
        msg = str(exc)
        if "not found" in msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=msg,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Unhandled exception during contract analysis: %s", str(exc), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Contract analysis failed: {str(exc)}",
        )
