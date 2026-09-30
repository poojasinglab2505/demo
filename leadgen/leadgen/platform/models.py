from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    users: Mapped[list["User"]] = relationship(back_populates="company", cascade="all, delete-orphan")
    agent_config: Mapped["AgentConfig"] = relationship(
        back_populates="company", uselist=False, cascade="all, delete-orphan"
    )
    leads: Mapped[list["Lead"]] = relationship(back_populates="company", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    company: Mapped["Company"] = relationship(back_populates="users")


class AgentConfig(Base):
    """Per-company targeting criteria and credentials for their AI lead-gen agent."""

    __tablename__ = "agent_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), unique=True)

    # Targeting criteria
    title_keywords: Mapped[str] = mapped_column(Text, default="")  # e.g. "CEO,VP Sales,Head of Marketing"
    industry_keywords: Mapped[str] = mapped_column(Text, default="")
    target_domains: Mapped[str] = mapped_column(Text, default="")  # company domains to search via Hunter
    company_size_min: Mapped[int] = mapped_column(Integer, default=0)
    company_size_max: Mapped[int] = mapped_column(Integer, default=0)  # 0 = no max
    revenue_min: Mapped[int] = mapped_column(Integer, default=0)
    revenue_max: Mapped[int] = mapped_column(Integer, default=0)  # 0 = no max
    enable_funding_signal_check: Mapped[bool] = mapped_column(default=False)

    # Schedule
    run_frequency_hours: Mapped[int] = mapped_column(Integer, default=24)
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_run_summary: Mapped[str] = mapped_column(Text, default="")

    # Credentials (encrypted at rest — see crypto.py). Each company brings its own keys.
    hunter_api_key_enc: Mapped[str] = mapped_column(Text, default="")
    apollo_api_key_enc: Mapped[str] = mapped_column(Text, default="")
    sendgrid_api_key_enc: Mapped[str] = mapped_column(Text, default="")
    anthropic_api_key_enc: Mapped[str] = mapped_column(Text, default="")
    from_email: Mapped[str] = mapped_column(String(255), default="")
    from_name: Mapped[str] = mapped_column(String(255), default="")
    company_postal_address: Mapped[str] = mapped_column(Text, default="")

    company: Mapped["Company"] = relationship(back_populates="agent_config")


class Lead(Base):
    __tablename__ = "platform_leads"
    __table_args__ = (UniqueConstraint("company_id", "email", name="uq_company_email"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)

    email: Mapped[str] = mapped_column(String(255))
    first_name: Mapped[str] = mapped_column(String(200), default="")
    last_name: Mapped[str] = mapped_column(String(200), default="")
    title: Mapped[str] = mapped_column(String(300), default="")
    lead_company: Mapped[str] = mapped_column(String(300), default="")  # the prospect's employer
    linkedin_url: Mapped[str] = mapped_column(String(500), default="")
    industry: Mapped[str] = mapped_column(String(200), default="")

    status: Mapped[str] = mapped_column(String(50), default="new")  # new | sent | bounced | unsubscribed
    icp_score: Mapped[int] = mapped_column(Integer, default=0)
    signal_notes: Mapped[str] = mapped_column(Text, default="")
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    company: Mapped["Company"] = relationship(back_populates="leads")
