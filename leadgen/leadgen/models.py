from dataclasses import dataclass, field


@dataclass
class Lead:
    first_name: str
    last_name: str
    title: str
    company: str
    email: str
    linkedin_url: str = ""
    industry: str = ""

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @classmethod
    def from_apollo_record(cls, record: dict) -> "Lead":
        org = record.get("organization") or {}
        return cls(
            first_name=record.get("first_name") or "",
            last_name=record.get("last_name") or "",
            title=record.get("title") or "",
            company=org.get("name") or record.get("organization_name") or "",
            email=record.get("email") or "",
            linkedin_url=record.get("linkedin_url") or "",
            industry=org.get("industry") or "",
        )
