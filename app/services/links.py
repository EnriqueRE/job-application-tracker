from sqlalchemy.orm import Session

from app.models import Application, AppLink
from app.schemas import LinkIn


def add_link(session: Session, application: Application, data: LinkIn) -> AppLink:
    link = AppLink(label=data.label, url=data.url)
    application.links.append(link)
    session.commit()
    return link


def get_link(session: Session, application: Application, link_id: int) -> AppLink | None:
    link = session.get(AppLink, link_id)
    return link if link is not None and link.application_id == application.id else None


def remove_link(session: Session, application: Application, link: AppLink) -> None:
    application.links.remove(link)
    session.commit()
