"""What a signed-in reader wants to see in the web app (lot 29): kept with the account.

Every field is applied by the interface's "My selection" view; empty filters mean "everything".
The newsletter keeps its own subscriber preferences until it is sent to accounts (lot 33).
"""

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, field_validator

from ..newsletter.models import DetailLevel
from ..taxonomy import Importance, normalize_categories


class ReaderPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    # Domains (taxonomy categories) the reader follows; empty: every domain.
    domains: tuple[str, ...] = ()
    # Hide news below this importance; None: every importance.
    min_importance: Optional[Importance] = None
    # False: only Confirmed and Reliable news (and nothing the AI did not analyze).
    include_unconfirmed: bool = True
    # brief: title, label, summary; complete: the context blocks too.
    detail_level: DetailLevel = DetailLevel.COMPLETE

    @field_validator("domains", mode="before")
    @classmethod
    def known_domains(cls, value: object) -> tuple[str, ...]:
        if not value:
            return ()
        if not isinstance(value, (list, tuple)):
            raise ValueError("domains must be a list")
        result: List[str] = []
        for entry in value:
            found = normalize_categories([entry])
            if not found:
                raise ValueError(f"unknown domain: {entry}")
            if found[0] not in result:
                result.append(found[0])
        return tuple(result)

    @property
    def filters(self) -> bool:
        """True when the selection differs from the whole edition."""
        return bool(self.domains) or self.min_importance is not None or not self.include_unconfirmed
