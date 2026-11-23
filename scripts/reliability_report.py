"""Summarize the installed worker's persisted observations without changing data."""
import json

from jobforge.reliability import report

if __name__ == "__main__":
    print(json.dumps(report(), indent=2))
