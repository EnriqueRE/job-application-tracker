from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Company, Contact
from app.schemas import ContactIn, ContactUpdate


def get_company(session: Session, company_id: int) -> Company | None:
    return session.get(Company, company_id)


def list_contacts(session: Session, company: Company) -> list[Contact]:
    query = select(Contact).where(Contact.company_id == company.id)
    return list(session.scalars(query.order_by(Contact.name, Contact.id)))


def get_contact(session: Session, contact_id: int) -> Contact | None:
    return session.get(Contact, contact_id)


def create_contact(session: Session, company: Company, data: ContactIn) -> Contact:
    contact = Contact(company=company, **data.model_dump())
    session.add(contact)
    session.commit()
    return contact


def update_contact(session: Session, contact: Contact, data: ContactUpdate) -> Contact:
    for name, value in data.model_dump(exclude_unset=True).items():
        setattr(contact, name, value)
    session.commit()
    return contact


def delete_contact(session: Session, contact: Contact) -> None:
    session.delete(contact)
    session.commit()
