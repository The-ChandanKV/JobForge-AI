"""Windowless Task Scheduler entry point with persistent rotating logs."""
import argparse
import logging
from logging.handlers import RotatingFileHandler

import uvicorn

from .config import DATA
from .worker import main as run_worker


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("role", choices=["api", "worker"])
    args = parser.parse_args()
    handler = RotatingFileHandler(DATA / f"windows-{args.role}.log", maxBytes=2_000_000,
                                  backupCount=3, encoding="utf-8")
    logging.basicConfig(level=logging.INFO, handlers=[handler],
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    if args.role == "worker":
        run_worker()
    else:
        uvicorn.run("jobforge.api:app", host="127.0.0.1", port=8000, log_config=None, access_log=False)


if __name__ == "__main__":
    main()
