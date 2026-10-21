"""Service management module: list, view, create, update and delete services.

Anyone logged in can read services. Changing them is staff only.
Updates use PATCH: send only the fields to change.
"""
from fastapi import APIRouter, Depends, Response

from app.deps import get_current_user, require_staff
from app.errors import ApiError
from app.models import Service, User
from app.schemas import ServiceIn, ServiceOut, ServiceUpdate
from app.store import db
from app.queue_activity import transaction

router = APIRouter(prefix="/services", tags=["services"])


def _out(service: Service) -> ServiceOut:
    return ServiceOut(id=service.id, name=service.name, description=service.description,
                      duration=service.duration, priority=service.priority, open=service.open)


def _find(service_id: int) -> Service:
    service = db.get_service(service_id)
    if service is None:
        raise ApiError(404, "not_found", "Service not found.")
    return service


def _check_name_free(name: str, except_id: int | None = None) -> None:
    clash = db.get_service_by_name(name)
    if clash is not None and clash.id != except_id:
        raise ApiError(409, "conflict", "A service with this name already exists.",
                       fields={"name": "A service with this name already exists."})


@router.get("", response_model=list[ServiceOut])
def list_services(user: User = Depends(get_current_user)):
    return [_out(s) for s in db.list_services()]


@router.get("/{service_id}", response_model=ServiceOut)
def get_service(service_id: int, user: User = Depends(get_current_user)):
    return _out(_find(service_id))


@router.post("", response_model=ServiceOut, status_code=201)
def create_service(body: ServiceIn, user: User = Depends(require_staff)):
    with transaction():
        _check_name_free(body.name)
        return _out(db.add_service(body.name, body.description, body.duration, body.priority))


@router.patch("/{service_id}", response_model=ServiceOut)
def update_service(service_id: int, body: ServiceUpdate, user: User = Depends(require_staff)):
    """Partial update: only the fields sent in the body are changed."""
    with transaction():
        service = _find(service_id)
        changes = {field: getattr(body, field) for field in body.model_fields_set}
        if "name" in changes:
            _check_name_free(changes["name"], except_id=service.id)
        for field, value in changes.items():
            setattr(service, field, value)
        return _out(service)


@router.delete("/{service_id}", status_code=204)
def delete_service(service_id: int, user: User = Depends(require_staff)):
    """Deletes the service even if students are waiting. The queue module hooks into
    db.service_deleted_hooks to cancel those entries and notify the students."""
    with transaction():
        _find(service_id)
        db.delete_service(service_id)
    return Response(status_code=204)
