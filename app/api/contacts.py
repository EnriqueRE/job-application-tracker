from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Company, Contact
from app.schemas import ContactIn, ContactOut, ContactUpdate
from app.services import contacts as service

router = APIRouter(prefix="/api", tags=["contacts"])

SessionDep = Annotated[Session, Depends(get_session)]


def company_or_404(session: Session, company_id: int) -> Company:
    company = service.get_company(session, company_id)
    if company is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Company not found")
    return company


def contact_or_404(session: Session, contact_id: int) -> Contact:
    contact = service.get_contact(session, contact_id)
    if contact is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Contact not found")
    return contact


@router.get("/companies/{company_id}/contacts", response_model=list[ContactOut])
def list_contacts(company_id: int, session: SessionDep) -> list[ContactOut]:
    company = company_or_404(session, company_id)
    return [ContactOut.model_validate(c) for c in service.list_contacts(session, company)]


@router.post(
    "/companies/{company_id}/contacts",
    status_code=status.HTTP_201_CREATED,
    response_model=ContactOut,
)
def create_contact(company_id: int, data: ContactIn, session: SessionDep) -> ContactOut:
    company = company_or_404(session, company_id)
    return ContactOut.model_validate(service.create_contact(session, company, data))


@router.patch("/contacts/{contact_id}", response_model=ContactOut)
def update_contact(contact_id: int, data: ContactUpdate, session: SessionDep) -> ContactOut:
    contact = contact_or_404(session, contact_id)
    return ContactOut.model_validate(service.update_contact(session, contact, data))


@router.delete("/contacts/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_contact(contact_id: int, session: SessionDep) -> Response:
    service.delete_contact(session, contact_or_404(session, contact_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
