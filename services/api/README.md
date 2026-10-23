# getter-api

FastAPI service for practice interviews. See the repository README for how to
run it.

- `interview/engine.py` runs the interview plan. Sections, questions, time
  limits and the follow-up budget are enforced in code; the model only decides
  whether to probe deeper and words the follow-up.
- `interview/grading.py` grades a finished transcript. Every score must quote
  the candidate's own words from a real turn (checked in code, with a repair
  retry), the verdict is computed from the scores in code, and an optional
  second grader flags disagreements. A failed grading never produces a score.
- `llm/` is the only code that talks to AI providers. Tasks
  (`interview_turn`, `grading`, `grading_check`) map to an ordered list of
  models in YAML.
- `content/` holds rubrics and templates. Change them only by pull request;
  every score records the rubric version and prompt version that produced it.

Evals: `uv run python -m getter_api.evals --config a.yaml --config b.yaml`.
The shipped cases are synthetic and only test the harness; real model choice
needs 20 to 30 transcripts graded by an experienced interviewer.
