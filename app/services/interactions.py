from datetime import date

from sqlalchemy.orm import Session

from app.models import Application, Interaction
from app.schemas import InteractionIn
from app.services.contacts import get_contact


class InvalidInteraction(ValueError):
    pass


def log_interaction(
    session: Session, application: Application, data: InteractionIn, *, today: date
) -> Interaction:
    occurred_on = data.occurred_on or today
    if occurred_on > today:
        raise InvalidInteraction("An interaction can't be in the future.")
    contact = None
    if data.contact_id is not None:
        contact = get_contact(session, data.contact_id)
        if contact is None or contact.company_id != application.company_id:
            raise InvalidInteraction(f"The contact must work at {application.company.name}.")
    interaction = Interaction(
        occurred_on=occurred_on, channel=data.channel, contact=contact, note=data.note
    )
    application.interactions.append(interaction)
    session.commit()
    return interaction


def get_interaction(
    session: Session, application: Application, interaction_id: int
) -> Interaction | None:
    interaction = session.get(Interaction, interaction_id)
    if interaction is None or interaction.application_id != application.id:
        return None
    return interaction


def delete_interaction(
    session: Session, application: Application, interaction: Interaction
) -> None:
    application.interactions.remove(interaction)
    session.commit()
