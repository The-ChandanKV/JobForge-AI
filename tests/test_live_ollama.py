import os

import pytest

from jobforge.models import Session
from jobforge.providers import save_job
from jobforge.resumes import generate
from jobforge.schemas import Fact, Generation, Options, Posting


@pytest.mark.skipif(not os.getenv("JOBFORGE_TEST_OLLAMA"), reason="Live Ollama model was not requested")
def test_live_ollama_orders_verified_facts_and_compiles_pdf(db_ready):
    facts = [
        Fact(category="personal", label="Name", value="Jordan Rao", verified=True),
        Fact(category="project", label="Web service", value="Built a Python and FastAPI service.", verified=True),
        Fact(category="project", label="Watercolor", value="Created watercolor paintings.", verified=True),
        Fact(category="skill", label="Database", value="SQL", verified=True),
        Fact(category="experience", label="False claim", value="Managed 500 employees.", verified=False),
    ]
    with Session.begin() as db:
        job = save_job(db, Posting(source_key="ollama:synthetic", source="test", company="Ollama synthetic test",
                                   role="Backend Engineer", description="Build Python and SQL web services."))
        job.match = {"matching_skills": ["Python", "SQL"]}
        resume = generate(db, job, [fact.model_dump() for fact in facts],
                          Options(provider="ollama", model=os.environ["JOBFORGE_TEST_OLLAMA"]),
                          Generation(instructions="Prioritize relevant web service experience."))
        assert resume.report["ai"]["provider"] == "ollama", resume.report["ai"]
        assert resume.report["ai"]["usage"]["output_tokens"] > 0
        assert resume.pdf.startswith(b"%PDF-") and resume.report["pages"] == 1
        assert "Managed 500 employees" not in resume.tex
        assert facts[1].id in {claim["id"] for claim in resume.report["claims"]}
