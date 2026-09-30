import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    apollo_api_key: str
    hunter_api_key: str
    sendgrid_api_key: str
    from_email: str
    from_name: str
    company_postal_address: str
    daily_send_limit: int
    send_delay_seconds: float
    icp_title_keywords: str
    icp_industry_keywords: str
    anthropic_api_key: str
    icebreaker_model: str

    @classmethod
    def load(cls) -> "Settings":
        return cls(
            apollo_api_key=os.environ.get("APOLLO_API_KEY", ""),
            hunter_api_key=os.environ.get("HUNTER_API_KEY", ""),
            sendgrid_api_key=os.environ.get("SENDGRID_API_KEY", ""),
            from_email=os.environ.get("FROM_EMAIL", ""),
            from_name=os.environ.get("FROM_NAME", ""),
            company_postal_address=os.environ.get("COMPANY_POSTAL_ADDRESS", ""),
            daily_send_limit=int(os.environ.get("DAILY_SEND_LIMIT", "50")),
            send_delay_seconds=float(os.environ.get("SEND_DELAY_SECONDS", "3")),
            icp_title_keywords=os.environ.get("ICP_TITLE_KEYWORDS", ""),
            icp_industry_keywords=os.environ.get("ICP_INDUSTRY_KEYWORDS", ""),
            anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
            icebreaker_model=os.environ.get("ICEBREAKER_MODEL", "claude-sonnet-5-5"),
        )
