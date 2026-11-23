import re
from datetime import UTC, datetime, timedelta

from .providers import fold
from .schemas import Posting, Preferences

SKILLS = ("Python", "SQL", "Java", "JavaScript", "TypeScript", "C++", "C#", "Go", "Rust", "FastAPI",
          "React", "Node.js", "Django", "Flask", "PostgreSQL", "MySQL", "MongoDB", "Redis", "Docker",
          "Kubernetes", "AWS", "Azure", "GCP", "PyTorch", "TensorFlow", "Git", "Linux", "Kafka", "GraphQL",
          "Spark", "Airflow", "ETL", "dbt", "Pandas", "Machine Learning", "NLP", "Scikit-learn", "Snowflake",
          "Kotlin", "Jetpack Compose", "Android SDK", "REST APIs", "Terraform", "Flink")
TRACKS = {
    "entry-level": r"\b(?:entry[ -]level|junior|associate|engineer i)\b",
    "graduate": r"\b(?:graduate|new grad|campus)\b",
    "backend": r"\bback[ -]?end\b",
    "full-stack": r"\bfull[ -]?stack\b",
    "data": r"\b(?:data engineer|data platform|analytics engineer)\b",
    "ai-ml": r"\b(?:ai|ml|machine learning|applied scientist)\b",
    "internship": r"\bintern(?:ship)?\b",
}
YEARS = re.compile(
    r"(?i)\b(\d{1,2})\s*(?:\+|[-–]\s*\d{1,2})?\s*years?\s+(?:of\s+)?"
    r"(?:relevant\s+|professional\s+|work\s+)?experience\b"
)
REQUIREMENT_LABEL = re.compile(
    r"(?i)^(required(?: skills| qualifications)?|minimum qualifications|must have|mandatory skills|"
    r"preferred(?: skills| qualifications)?|nice to have|bonus points)\s*(?::\s*(.*)|$)"
)


def requirement_lines(description):
    sections = {"required": [], "preferred": [], "uncertain": []}
    section = "uncertain"
    partitions = re.split(r"[\n;]+|(?<=\.)\s+(?=(?:required|preferred|minimum qualifications|nice to have)\b)",
                          description, flags=re.I)
    for raw in partitions:
        line = raw.strip().lstrip("-*• ").strip()
        if not line:
            continue
        heading = REQUIREMENT_LABEL.fullmatch(line)
        target = section
        if heading:
            target = "preferred" if heading[1].lower().startswith(("preferred", "nice", "bonus")) else "required"
            line = heading[2] or ""
            if not line:
                section = target
        elif re.match(r"(?i)^(responsibilities|benefits|about us|about the role)\s*:?\s*$", line):
            section = "uncertain"
        if line:
            if not heading and re.search(r"(?i)\b(?:nice to have|preferred|optional|a plus)\b", line):
                target = "preferred"
            elif not heading and target != "preferred" and re.search(
                r"(?i)\b(?:must have|must be|must hold|minimum of|at least|required to)\b", line
            ):
                target = "required"
            sections[target].append(line)
    return sections


def minimum_years(sections, category):
    return max((int(match[1]) for line in sections[category] for match in YEARS.finditer(line)), default=None)


def expired(value):
    if not value:
        return False
    try:
        deadline = datetime.fromisoformat(value)
    except ValueError:
        return False
    if len(value) == 10:
        deadline += timedelta(days=1)
    return (deadline if deadline.tzinfo else deadline.replace(tzinfo=UTC)) <= datetime.now(UTC)


def has_skill(text, skill):
    return bool(re.search(r"\b(?:Go(?:lang)?|golang)\b", text)) if skill == "Go" else contains(text, skill)


def contains(text, value):
    return bool(re.search(r"(?<!\w)" + re.escape(value.casefold()) + r"(?!\w)", text.casefold()))


def profile_values(facts, category):
    return [f["value"] for f in facts if f["verified"] and f["category"] == category]


def profile_field(facts, label, category=None):
    return next((f["value"] for f in facts if f["verified"] and f["label"].lower() == label.lower()
                 and (category is None or f["category"] == category)), None)


def analyze(posting: Posting, facts, preferences: Preferences, threshold):
    desc = posting.description
    corpus = f"{posting.role} {desc}"
    requirements = requirement_lines(desc)
    required_lines = requirements["required"]
    preferred_lines = requirements["preferred"]
    verified_skills = profile_values(facts, "skill")
    vocabulary = list(dict.fromkeys([*SKILLS, *verified_skills]))
    alternatives = {}
    for line in required_lines:
        if re.search(r"(?i)\b(?:at least one|one of|either)\b", line) and not re.search(r"(?i)\band\b|;", line):
            skills = tuple(skill for skill in vocabulary if has_skill(line, skill))
            if len(skills) > 1:
                alternatives[line] = skills
    named_in_alternatives = {skill for group in alternatives.values() for skill in group}
    required = [s for s in vocabulary if any(has_skill(line, s) for line in required_lines if line not in alternatives)]
    preferred = [s for s in vocabulary if s not in required and s not in named_in_alternatives and any(has_skill(line, s) for line in preferred_lines)]
    mentioned = [s for s in vocabulary if has_skill(corpus, s)]
    matching = [s for s in mentioned if any(has_skill(v, s) for v in verified_skills)]
    missing = [s for s in required if s not in matching]
    groups = list(dict.fromkeys(alternatives.values()))
    unmet_groups = [group for group in groups if not set(group).intersection(matching)]
    fail, review = [], []
    if expired(posting.deadline):
        fail.append("The employer's application deadline has passed.")
    if missing:
        review.append("Verify mandatory skills: " + ", ".join(missing))
    if unmet_groups:
        review.extend("Verify one of the listed alternatives: " + ", ".join(group) for group in unmet_groups)
    if not any(f["verified"] for f in facts):
        review.append("Verify the master profile.")
    years = minimum_years(requirements, "required")
    uncertain_years = minimum_years(requirements, "uncertain")
    if years is not None:
        available = profile_field(facts, "Years of experience")
        if not available or not re.fullmatch(r"\d{1,2}(?:\.\d+)?", available):
            review.append(f"Verify years of experience, minimum {years}.")
        elif float(available) < years:
            fail.append(f"Verified experience is below the minimum of {years} years.")
    if uncertain_years is not None:
        available = profile_field(facts, "Years of experience")
        if not available or not re.fullmatch(r"\d{1,2}(?:\.\d+)?", available) or float(available) < uncertain_years:
            review.append("Check whether the stated experience requirement is mandatory.")
    graduation = re.search(r"(?i)\bgraduat\w*\s+(?:(?:in|by|after|before)\s+)?\b(20\d{2})\b",
                           "\n".join([*required_lines, *requirements["uncertain"]]))
    if graduation:
        actual = profile_field(facts, "Graduation year")
        if actual != graduation[1]:
            review.append(f"Check whether the graduation-year restriction ({graduation[1]}) applies.")
    degree = re.search(r"(?i)\b(bachelor|master|doctorate|phd)\b.{0,35}\b(?:required|degree)\b", desc)
    if degree and not any(contains(v, degree[1]) for v in profile_values(facts, "education")):
        review.append("Check degree requirement: " + degree[0])
    eligibility_text = "\n".join([*required_lines, *requirements["uncertain"]])
    authorization = re.search(r"(?i)\b(?:authorized|authorised|right) to work in ([^.;\n,]+)", eligibility_text)
    verified_locations = profile_field(facts, "Authorized work locations", "authorization") or ""
    auth_matches = authorization and fold(authorization[1]) in {fold(location) for location in verified_locations.split(",")}
    if re.search(r"(?i)\b(work authori[sz]ation|no sponsorship|visa sponsorship|citizen(?:ship)?|right to work|authori[sz]ed to work)\b",
                 eligibility_text) and (not auth_matches or re.search(r"(?i)\b(sponsorship|citizen)", eligibility_text)):
        review.append("Review work authorization and sponsorship against the posting.")
    geographic_requirement = re.search(
        r"(?i)\b(?:(?:reside|located|based)\s+in|only\s+(?:in|within))\b(?:\s+[^.!?,;\n]{1,100})?", desc)
    if geographic_requirement:
        review.append("Review geographic restrictions.")
    if (re.search(r"(?i)\b(?:mandatory|required|must hold)\b.{0,40}\b(?:certification|licen[cs]e|clearance)\b|\bcertification\s+required\b", desc)
            or any(re.search(r"(?i)\b(?:certification|licen[cs]e|clearance)\b", line) for line in required_lines)):
        review.append("Review required certification, license, or clearance.")
    if any(line not in alternatives and not YEARS.search(line) and not (auth_matches and authorization[0].casefold() in line.casefold())
           and not all(any(has_skill(fragment, skill) for skill in required)
                       for fragment in re.split(r"[,/]", line) if fragment.strip())
           for line in required_lines):
        review.append("Review mandatory requirements outside the recognized evidence.")
    if preferences.employment and posting.employment and not any(
        fold(wanted) in fold(posting.employment) for wanted in preferences.employment
    ):
        fail.append("Employment type is outside your preferences.")
    elif preferences.employment and not posting.employment:
        review.append("Employment type is missing.")

    relevant = {}
    for cat in ("project", "experience", "education"):
        relevant[cat] = [f["value"] for f in facts if f["verified"] and f["category"] == cat
                         and any(contains(f["value"], s) for s in mentioned)]
    role_aligned = (any(contains(posting.role, role) for role in preferences.roles)
                    or any(re.search(TRACKS[track], f"{posting.role} {posting.employment}", re.I) for track in preferences.career_tracks))
    scored = required if required or groups else [skill for skill in mentioned if skill not in preferred]
    slots = len(scored) + len(groups)
    covered = len(set(matching) & set(scored)) + len(groups) - len(unmet_groups)
    skills_score = round(55 * covered / slots) if slots else 0
    components = {
        "skills": skills_score, "projects": min(15, 8 * len(relevant["project"])),
        "experience": min(10, 5 * len(relevant["experience"])),
        "education": min(5, 5 * len(relevant["education"])),
        "role": 10 if role_aligned else 0,
        "preferred": round(5 * sum(s in matching for s in preferred) / len(preferred)) if preferred else 0,
    }
    score = sum(components.values())
    eligibility = "INELIGIBLE" if fail else "NEEDS_REVIEW" if review else "ELIGIBLE"
    recommendation = "PREPARE_APPLICATION" if eligibility == "ELIGIBLE" and score >= threshold else "REVIEW"
    return {
        "eligibility": eligibility, "match_score": score, "components": components, "matching_skills": matching,
        "alternative_skill_groups": [list(group) for group in groups],
        "required_skills": required, "missing_skills": missing, "preferred_skills": preferred,
        "relevant_projects": relevant["project"], "concerns": fail + review,
        "experience_years": years,
        "degree_requirement": degree[0] if degree else None,
        "location_requirement": geographic_requirement[0] if geographic_requirement else None,
        "authorization_requirement": authorization[0] if authorization else None,
        "requirement_evidence": {category: lines[:15] for category, lines in requirements.items()},
        "confidence": "REVIEW" if eligibility == "NEEDS_REVIEW" else "RULE_VERIFIED",
        "graduation_year": int(graduation[1]) if graduation else None,
        "suggestions": ["Confirm supporting evidence for " + skill for skill in missing],
        "recommendation": recommendation,
        "reason": "Meets the configured relevance threshold and detected eligibility checks."
                  if recommendation == "PREPARE_APPLICATION" else "Review the eligibility findings and score breakdown.",
    }


def shortlist(posting, preferences):
    def any_match(text, values):
        return any(contains(text, value) for value in values if value.strip())

    if preferences.roles and not any_match(posting.role, preferences.roles):
        return False
    if preferences.career_tracks and not any(re.search(TRACKS[track], f"{posting.role} {posting.employment}", re.I)
                                              for track in preferences.career_tracks):
        return False
    if preferences.exclude_senior_roles and re.search(r"\b(?:senior|sr|staff|principal|director|architect|manager)\b", posting.role, re.I):
        return False
    if expired(posting.deadline):
        return False
    if preferences.maximum_mandatory_years is not None or preferences.minimum_mandatory_years is not None:
        years = minimum_years(requirement_lines(posting.description), "required")
        if years is not None and (
            (preferences.maximum_mandatory_years is not None and years > preferences.maximum_mandatory_years)
            or (preferences.minimum_mandatory_years is not None and years < preferences.minimum_mandatory_years)
        ):
            return False
    if preferences.locations and not any_match(posting.location, preferences.locations):
        return False
    if preferences.work_modes and posting.work_mode not in preferences.work_modes:
        return False
    if preferences.levels and not any_match(posting.role + " " + posting.description, preferences.levels):
        return False
    if preferences.target_companies and not any_match(posting.company, preferences.target_companies):
        return False
    if any_match(posting.company, preferences.excluded_companies):
        return False
    if any_match(posting.role, preferences.excluded_roles):
        return False
    if any_match(posting.role + " " + posting.description, preferences.excluded_keywords):
        return False
    if (preferences.min_salary is not None and preferences.salary_currency
            and posting.salary_currency.casefold() == preferences.salary_currency.casefold()
            and posting.salary_max is not None and posting.salary_max < preferences.min_salary):
        return False
    if preferences.recent_days:
        try:
            posted = datetime.fromisoformat(posting.posted or "")
            posted = posted.replace(tzinfo=UTC) if posted.tzinfo is None else posted
            if posted < datetime.now(UTC) - timedelta(days=preferences.recent_days):
                return False
        except ValueError:
            return False
    return True


def evaluate_saved_job(job, facts, preferences, threshold):
    cached = job.match.get("semantic") if job.match else None
    job.match = analyze(Posting.model_validate(job.detail), facts, preferences, threshold)
    if cached:
        job.match = {**job.match, "semantic": cached}
    if job.status in {"DISCOVERED", "SHORTLISTED", "NEEDS_REVIEW"}:
        if job.match["eligibility"] == "NEEDS_REVIEW":
            job.status = "NEEDS_REVIEW"
        elif job.match["recommendation"] == "PREPARE_APPLICATION":
            job.status = "SHORTLISTED"
        else:
            job.status = "DISCOVERED"
