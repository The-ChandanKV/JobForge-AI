"""Employer-supplied careers sources used for discovery suggestions."""
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from .models import Log, Profile
from .providers import fetch_board
from .schemas import Options, Preferences, Source


CATALOG = {
    "bosch": ("Bosch Group", "smartrecruiters", "BoschGroup", "Industrial technology", "India Germany Global", "Software Engineer Embedded Data", "https://www.bosch.com/careers/faq/"),
    "the-codest": ("The Codest", "recruitee", "thecodest", "Software consulting", "Poland Europe Remote", "Backend Full Stack Data", "https://thecodest.recruitee.com/"),
    "datadog": ("Datadog", "greenhouse", "datadog", "Cloud infrastructure", "USA Europe", "Software Engineer Backend Data", "https://careers.datadoghq.com/"),
    "cloudflare": ("Cloudflare", "greenhouse", "cloudflare", "Internet infrastructure", "USA Europe India Global", "Software Engineer Backend Systems", "https://www.cloudflare.com/careers/jobs/"),
    "stripe": ("Stripe", "greenhouse", "stripe", "Financial technology", "USA Europe India Global", "Software Engineer Backend Full Stack Data", "https://stripe.com/jobs"),
    "anthropic": ("Anthropic", "greenhouse", "anthropic", "Artificial intelligence", "USA UK Global", "Software Engineer AI ML Data", "https://www.anthropic.com/careers"),
}


def company_records(db, options, filters):
    preferences = Preferences.model_validate(db.get(Profile, 1).preferences)
    records = []
    for key, (company, provider, board, industry, locations, roles, careers) in CATALOG.items():
        if any(value and value.casefold() not in field.casefold()
               for value, field in zip(filters, (company, industry, locations, roles), strict=True)):
            continue
        monitored = any(row.enabled and row.provider == provider and row.board.casefold() == board.casefold()
                        for row in options.sources)
        group = ("excluded" if company.casefold() in {item.casefold() for item in preferences.excluded_companies} else
                 "priority" if company.casefold() in {item.casefold() for item in preferences.priority_companies} else "regular")
        records.append({"key": key, "company": company, "provider": provider, "board": board, "industry": industry,
                        "locations": locations, "roles": roles, "careers": careers, "enabled": monitored, "group": group,
                        "verified_at": latest_verification(db, provider, board)})
    targets = {name.casefold() for name in preferences.target_companies}
    industries = {name.casefold() for name in preferences.industries}
    return sorted(records, key=lambda row: (row["group"] == "excluded", row["group"] != "priority",
                  row["company"].casefold() not in targets, row["industry"].casefold() not in industries,
                  row["company"].casefold()))


def latest_verification(db, provider, board):
    return db.scalar(select(Log.created).where(Log.kind == "board_verified",
                     Log.detail["provider"].as_string() == provider,
                     Log.detail["board"].as_string() == board.casefold()).order_by(Log.created.desc()).limit(1))


def recently_verified(db, provider, board):
    value = latest_verification(db, provider, board)
    return bool(value and datetime.fromisoformat(value) >= datetime.now(UTC) - timedelta(days=7))


def catalog_source(key):
    if key not in CATALOG:
        raise ValueError("Choose a known employer board.")
    company, provider, board, *_ = CATALOG[key]
    return Source(provider=provider, board=board, company=company)


def verify_catalog_source(db_session, key):
    source = catalog_source(key)
    rows, complete = fetch_board(source)
    if not rows or not any(row.url for row in rows):
        raise ValueError("This feed did not return a verifiable public posting.")
    with db_session.begin() as db:
        db.add(Log(kind="board_verified", message="Public employer board verified",
                   detail={"provider": source.provider, "board": source.board.casefold(),
                           "careers": CATALOG[key][-1], "sample_size": len(rows)}))
    return {"complete": complete, "jobs": [{"role": row.role, "location": row.location, "url": str(row.url)}
                                          for row in rows[:8] if row.url]}


def update_monitor(db, settings, key, enabled, group):
    source = catalog_source(key)
    options = Options.model_validate(settings.options)
    current = [row for row in options.sources if (row.provider, row.board.casefold()) !=
               (source.provider, source.board.casefold())]
    old = next((item for item in options.sources if item.provider == source.provider and
                item.board.casefold() == source.board.casefold()), None)
    if enabled and (group == "excluded" or (not (old and old.enabled) and
                    not recently_verified(db, source.provider, source.board))):
        raise ValueError("Verify the board before enabling an eligible employer.")
    if enabled and len(current) >= 20:
        raise ValueError("Remove another source before enabling this employer.")
    if enabled or old:
        current.append((old or source).model_copy(update={"enabled": enabled}))
    settings.options = options.model_copy(update={"sources": current}).model_dump(mode="json")
    profile = db.get(Profile, 1)
    preferences = Preferences.model_validate(profile.preferences)
    for name, target_group in (("priority_companies", "priority"), ("excluded_companies", "excluded")):
        values = [item for item in getattr(preferences, name) if item.casefold() != source.company.casefold()]
        if group == target_group:
            values.append(source.company)
        setattr(preferences, name, values)
    profile.preferences = Preferences.model_validate(preferences.model_dump()).model_dump()
