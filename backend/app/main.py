"""Company Brain backend — minimal Phase 0 skeleton.

This is the smallest FastAPI app that proves the deploy pipeline end-to-end.
Real surfaces (ask/see/brief/admin), DB access, inference, integrations are
added in subsequent sessions per the build order in CLAUDE.md.
"""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Company Brain", version="0.1.1")

# Phase 0: the frontend is served from S3 (different origin from the ALB).
# Allow all origins because (a) team-only, (b) frontend URL rotates with
# every `make up`. Phase 1 (with a custom domain) tightens to a specific origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "environment": os.environ.get("ENVIRONMENT", "unknown"),
        "region": os.environ.get("AWS_REGION", "unknown"),
    }
