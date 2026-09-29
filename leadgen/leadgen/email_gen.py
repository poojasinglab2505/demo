from pathlib import Path

from jinja2 import Environment, FileSystemLoader

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"

_env = Environment(loader=FileSystemLoader(TEMPLATE_DIR), autoescape=False)


def render_email(lead, pitch: str, sender_name: str, company_postal_address: str) -> tuple[str, str]:
    """Returns (subject, body) for a lead."""
    template = _env.get_template("cold_email.txt.j2")
    rendered = template.render(
        first_name=lead["first_name"] or "there",
        title=lead["title"] or "a leader",
        company=lead["company"] or "your company",
        pitch=pitch,
        sender_name=sender_name,
        company_postal_address=company_postal_address,
    )
    subject_line, _, body = rendered.partition("\n")
    subject = subject_line.removeprefix("Subject:").strip()
    return subject, body.strip()
