from datetime import UTC, datetime, timedelta

from . import greenhouse
from .matching import shortlist
from .schemas import Posting, Preferences, SubmissionPolicy


class PolicyRefusal(ValueError):
    pass


def fact_digest(fact):
    return greenhouse.digest({key: fact[key] for key in ("id", "category", "label", "value")})


def posting_digest(job):
    return greenhouse.digest(job.detail)


def create_policy(request, profile, prepared):
    board = greenhouse.verified_board()
    current = datetime.now(UTC)
    if not board:
        raise PolicyRefusal("The employer integration needs credentialed authorization and a verification reference.")
    if not current < request.expires <= current + timedelta(days=30):
        raise PolicyRefusal("Set a policy expiry within the next 30 days.")
    keys = list(dict.fromkeys(request.job_keys))
    if set(keys) != prepared.keys() or any(not key.startswith(f"greenhouse:{board}:") for key in keys):
        raise PolicyRefusal("Each exact job key must have a prepared form on the authorized board.")
    if any(job.company.casefold() != request.employer.strip().casefold() for job, _ in prepared.values()):
        raise PolicyRefusal("Each prepared job must match the exact named employer.")
    verified = {fact["id"]: fact_digest(fact) for fact in profile.facts if fact["verified"]}
    if set(request.fact_ids) - verified.keys():
        raise PolicyRefusal("Every approved field must reference a current verified profile fact.")
    return SubmissionPolicy(
        integration=request.integration, board=board, employer=request.employer.strip(), job_keys=keys,
        approved_facts={key: verified[key] for key in request.fact_ids},
        form_digests={key: app.summary["form_digest"] for key, (_, app) in prepared.items()},
        posting_digests={key: posting_digest(job) for key, (job, _) in prepared.items()},
        evidence=greenhouse.verification_reference(), expires=request.expires, created=current,
        daily_limit=request.daily_limit, minimum_score=request.minimum_score,
    )


def check_policy(options, job, resume, profile, application, form, values, match):
    policy = options.submission_policy
    if options.automation_mode != "AUTHORIZED_AUTO_SUBMIT" or not policy:
        raise PolicyRefusal("An explicit submission policy is required.")
    if policy.revoked or policy.expires <= datetime.now(UTC):
        raise PolicyRefusal("The submission policy expired or was revoked.")
    key = job.detail.get("source_key", job.source_key)
    if (policy.board != greenhouse.verified_board() or policy.evidence != greenhouse.verification_reference()
            or application.summary.get("integration") != policy.integration
            or key not in policy.job_keys or job.company.casefold() != policy.employer.casefold()):
        raise PolicyRefusal("The job or integration is outside the exact policy scope.")
    if (policy.form_digests.get(key) != form["form_digest"]
            or policy.posting_digests.get(key) != posting_digest(job)):
        raise PolicyRefusal("The employer posting or form changed after the policy was approved.")
    if (match["eligibility"] != "ELIGIBLE" or match["match_score"] < max(policy.minimum_score, options.min_match_score)
            or not shortlist(Posting.model_validate(job.detail), Preferences.model_validate(profile.preferences))):
        raise PolicyRefusal("The job no longer meets the policy's eligibility or relevance settings.")
    approved = policy.approved_facts
    if any(approved.get(fact["id"]) != fact_digest(fact) for fact in resume.report["claims"]):
        raise PolicyRefusal("The exact resume contains profile facts outside the policy.")
    for key, value in values.items():
        label = greenhouse.CONTACT_FIELDS[key].casefold()
        if not any(fact["verified"] and fact["category"] == "personal" and fact["label"].casefold() == label
                   and fact["value"].strip() == value and approved.get(fact["id"]) == fact_digest(fact)
                   for fact in profile.facts):
            raise PolicyRefusal("An outgoing contact field is outside the policy.")
    return policy
