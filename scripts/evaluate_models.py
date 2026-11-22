"""Compare Ollama ranking on isolated synthetic records and real compiled PDFs."""
import argparse
import json
import os
from pathlib import Path
from statistics import median
from tempfile import TemporaryDirectory
from time import monotonic


def evaluate(models):
    from jobforge.matching import analyze
    from jobforge.models import Base, Job, Session, engine
    from jobforge.resumes import generate
    from jobforge.schemas import Fact, Generation, Options, Posting, Preferences

    fixtures = json.loads(Path("tests/fixtures/model_evaluation.json").read_text(encoding="utf-8"))
    Base.metadata.create_all(engine)
    report = []
    for model in models:
        rows = []
        for example in fixtures:
            skills = example["required"]
            inputs = [
                ("personal", "Name", "Jordan Synthetic"),
                ("project", "Portfolio design", "Created watercolor illustrations for a school exhibition."),
                ("project", "Target project", "- I " + example["target"][0].lower() + example["target"][1:]),
                ("project", "Systems project", "Documented shell workflows and accessibility tests in a student lab."),
                ("experience", "Years of experience", "1"),
                *[("skill", value, value) for value in skills],
            ]
            facts = [Fact(category=category, label=label, value=value, verified=True).model_dump()
                     for category, label, value in inputs]
            posting = Posting(source_key=f"benchmark:{model}:{len(rows)}", source="manual", company="Synthetic employer",
                              role=example["role"], description=example["description"])
            match = analyze(posting, facts, Preferences(roles=[example["role"]]), 80)
            with Session.begin() as db:
                job = Job(source_key=posting.source_key, fingerprint="synthetic", company=posting.company,
                          role=posting.role, detail=posting.model_dump(mode="json"), match=match)
                db.add(job)
                db.flush()
                start = monotonic()
                result = generate(db, job, facts, Options(provider="ollama", model=model), Generation())
                seconds = round(monotonic() - start, 2)
                ai = result.report["ai"]
                projects = {f["id"] for f in facts if f["category"] == "project"}
                ranked = next((key for key in ai["ranked_fact_ids"] if key in projects), None)
                quality = result.report["quality"]
                rows.append({
                    "role": example["role"], "seconds_including_pdf": seconds, "provider": ai["provider"],
                    "eligibility_correct": match["eligibility"] == example["eligibility"],
                    "requirements_correct": all(set(match[key + "_skills"]) == set(example[key])
                                                for key in ("required", "preferred")),
                    "relevant_project_first": ranked == facts[2]["id"],
                    "factual_pdf": quality["unsupported_claims"] == 0 and example["target"] in result.tex,
                    "clean_layout": quality["text_extractable"] and not quality["page_overflow"]
                                    and not quality["formatting_warnings"],
                })
        report.append({"model": model, "median_seconds_including_pdf": median(
            row["seconds_including_pdf"] for row in rows), "fixtures": rows})
    engine.dispose()
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("models", nargs="+")
    args = parser.parse_args()
    with TemporaryDirectory(prefix="jobforge-model-evaluation-") as folder:
        os.environ["JOBFORGE_DATA"] = folder
        os.environ["DATABASE_URL"] = "sqlite:///" + (Path(folder) / "evaluation.sqlite3").as_posix()
        result = evaluate(args.models)
        print(json.dumps(result, indent=2))
