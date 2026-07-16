from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    File,
    Form,
    HTTPException,
    Response,
    UploadFile,
    status,
)
from sqlalchemy import delete, select

from app.api.deps import DB, CurrentUser
from app.api.routes.subjects import owned_subject
from app.core.config import settings
from app.db.session import SessionFactory
from app.models import (
    DocumentChunk,
    Material,
    MaterialKind,
    ProcessingStatus,
    ProgressEvent,
    ProgressEventType,
)
from app.schemas import MaterialRead
from app.services import (
    ChromaVectorStore,
    GeminiService,
    LearningEngine,
    LocalStorage,
    ServiceError,
    UploadValidationError,
    chunk_document,
    extract_document,
)

router = APIRouter(prefix="/subjects/{subject_id}/materials", tags=["materials"])
storage = LocalStorage(settings)
gemini = GeminiService(settings)
vectors = ChromaVectorStore(settings)
learning_engine = LearningEngine(gemini, vectors)


async def owned_material(db: DB, subject_id: UUID, material_id: UUID) -> Material:
    material = await db.scalar(
        select(Material).where(Material.id == material_id, Material.subject_id == subject_id)
    )
    if material is None:
        raise HTTPException(status_code=404, detail="Material not found")
    return material


async def process_material_record(material_id: UUID, user_id: UUID) -> None:
    """Extract, persist, embed, and index one material in an isolated transaction."""

    async with SessionFactory() as db:
        material = await db.get(Material, material_id)
        if material is None:
            return
        material.status = ProcessingStatus.PROCESSING
        material.error_message = None
        await db.commit()
        try:
            async with storage.materialize(material.storage_key) as path:
                document = await extract_document(path)
            chunks = chunk_document(document)
            indexed = await learning_engine.index_chunks(
                subject_id=str(material.subject_id),
                material_id=str(material.id),
                material_name=material.original_name,
                chunks=chunks,
            )
            await db.execute(delete(DocumentChunk).where(DocumentChunk.material_id == material.id))
            db.add_all(
                [
                    DocumentChunk(
                        material_id=material.id,
                        subject_id=material.subject_id,
                        chunk_index=chunk.index,
                        text=chunk.text,
                        token_count=chunk.token_estimate,
                        page_number=chunk.page_number,
                        vector_id=f"{material.id}:{chunk.index}",
                        extra_data={
                            **chunk.metadata,
                            "start_char": chunk.start_char,
                            "end_char": chunk.end_char,
                        },
                    )
                    for chunk in chunks
                ]
            )
            material.status = ProcessingStatus.READY
            material.extracted_chars = len(document.text)
            material.page_count = len(document.pages)
            material.extra_data = {
                **document.metadata,
                "chunk_count": len(chunks),
                "indexed_chunks": indexed["indexed_chunks"],
            }
            db.add(
                ProgressEvent(
                    user_id=user_id,
                    subject_id=material.subject_id,
                    event_type=ProgressEventType.MATERIAL_PROCESSED,
                    event_data={"material_id": str(material.id), "chunks": len(chunks)},
                )
            )
            await db.commit()
        except Exception as exc:
            await db.rollback()
            material = await db.get(Material, material_id)
            if material is not None:
                material.status = ProcessingStatus.FAILED
                material.error_message = (str(exc) or "Material processing failed")[:2000]
                await db.commit()


@router.get("", response_model=list[MaterialRead])
async def list_materials(
    subject_id: UUID,
    current_user: CurrentUser,
    db: DB,
) -> list[Material]:
    await owned_subject(db, current_user.id, subject_id)
    result = await db.scalars(
        select(Material)
        .where(Material.subject_id == subject_id)
        .order_by(Material.created_at.desc())
    )
    return list(result)


@router.post("", response_model=list[MaterialRead], status_code=status.HTTP_201_CREATED)
async def upload_materials(
    subject_id: UUID,
    current_user: CurrentUser,
    db: DB,
    background_tasks: BackgroundTasks,
    kind: Annotated[MaterialKind, Form()],
    files: Annotated[list[UploadFile], File()],
    process_now: Annotated[bool, Form()] = True,
) -> list[Material]:
    await owned_subject(db, current_user.id, subject_id)
    if not files:
        raise HTTPException(status_code=422, detail="Choose at least one file")
    if len(files) > 12:
        raise HTTPException(status_code=422, detail="Upload at most 12 files at a time")
    saved_keys: list[str] = []
    materials: list[Material] = []
    try:
        for upload in files:
            stored = await storage.save_upload(
                upload,
                filename=upload.filename or "material",
                content_type=upload.content_type,
                prefix=f"{current_user.id}/{subject_id}",
            )
            saved_keys.append(stored.key)
            material = Material(
                subject_id=subject_id,
                kind=kind,
                original_name=stored.original_name,
                storage_key=stored.key,
                content_type=stored.content_type,
                size_bytes=stored.size_bytes,
                checksum_sha256=stored.sha256,
            )
            db.add(material)
            materials.append(material)
            await upload.close()
        await db.commit()
        for material in materials:
            await db.refresh(material)
            if process_now:
                background_tasks.add_task(process_material_record, material.id, current_user.id)
        return materials
    except UploadValidationError as exc:
        await db.rollback()
        for key in saved_keys:
            await storage.delete(key)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ServiceError as exc:
        await db.rollback()
        for key in saved_keys:
            await storage.delete(key)
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/{material_id}/process", response_model=MaterialRead)
async def process_material_endpoint(
    subject_id: UUID,
    material_id: UUID,
    current_user: CurrentUser,
    db: DB,
) -> Material:
    await owned_subject(db, current_user.id, subject_id)
    await owned_material(db, subject_id, material_id)
    await process_material_record(material_id, current_user.id)
    db.expire_all()
    material = await owned_material(db, subject_id, material_id)
    if material.status == ProcessingStatus.FAILED:
        detail = material.error_message or "Material processing failed"
        if "not configured" in detail.lower():
            raise HTTPException(status_code=503, detail=detail)
        raise HTTPException(status_code=422, detail=detail)
    return material


@router.delete("/{material_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_material(
    subject_id: UUID,
    material_id: UUID,
    current_user: CurrentUser,
    db: DB,
) -> Response:
    await owned_subject(db, current_user.id, subject_id)
    material = await owned_material(db, subject_id, material_id)
    storage_key = material.storage_key
    await db.delete(material)
    await db.commit()
    await storage.delete(storage_key)
    try:
        await vectors.delete_material(str(material_id))
    except ServiceError:
        pass
    return Response(status_code=status.HTTP_204_NO_CONTENT)
