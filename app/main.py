# ================================================================
# FILE: app/main.py
# PURPOSE: FastAPI server that wraps environment into HTTP API
#
# THINK OF IT AS: The waiter in a restaurant
#   Agent (customer) sends HTTP requests
#   FastAPI (waiter) receives them
#   env.py (kitchen) processes them
#   FastAPI sends response back to agent
#
# 3 ENDPOINTS:
#   POST /reset  → start fresh episode
#   POST /step   → submit action get reward
#   GET  /state  → check current progress
#
# WHY FASTAPI:
#   Very fast
#   Auto validates data types using Pydantic
#   Auto generates API documentation
#   Industry standard for AI projects
# ================================================================

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn

from app.env import CodeReviewEnv
from app.models import (
    Action,
    Observation,
    StepResult,
    State
)


# ================================================================
# GLOBAL ENVIRONMENT INSTANCE
# PURPOSE: One shared environment for all requests
#
# WHY GLOBAL:
#   HTTP is stateless — each request knows nothing about previous
#   We need ONE env instance that persists between requests
#   So agent can reset() then step() and env remembers state
#
# Think of it like:
#   A single exam hall that persists between questions
#   Not a new hall created for each question!
# ================================================================
env = None


# ================================================================
# LIFESPAN — runs when server starts and stops
# PURPOSE: Initialize environment when server boots up
#
# WHY LIFESPAN:
#   We need env ready before any request comes in
#   lifespan handles startup and shutdown cleanly
# ================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):

    # This runs when server STARTS
    global env
    # Start with "all" difficulty so all bugs available
    # Judges can specify task in reset request
    env = CodeReviewEnv(task="all", seed=42)
    print("Environment loaded successfully!")
    print(f"Total bugs available: {len(env.bugs)}")

    yield  # Server runs here

    # This runs when server STOPS
    print("Server shutting down!")


# ================================================================
# CREATE FASTAPI APP
# PURPOSE: The main application object
# ================================================================
app = FastAPI(
    title="Code Review Agent Environment",
    description="An OpenEnv environment where AI agents learn to review code bugs",
    version="1.0.0",
    lifespan=lifespan
)


# ================================================================
# CORS MIDDLEWARE
# PURPOSE: Allow requests from any origin
#
# WHY NEEDED:
#   HuggingFace and judges might send requests from different URLs
#   CORS restrictions would block them without this!
# ================================================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)


# ================================================================
# ENDPOINT 1: GET /
# PURPOSE: Health check — is server alive?
#
# WHY NEEDED:
#   HuggingFace pings this to check if space is running
#   Judges check this before testing your environment
#   Must return 200 status or you get DISQUALIFIED!
# ================================================================
@app.get("/")
async def root():
    return {
        "status": "running",
        "environment": "Code Review Agent",
        "version": "1.0.0",
        "endpoints": {
            "reset": "POST /reset",
            "step": "POST /step",
            "state": "GET /state"
        }
    }


# ================================================================
# ENDPOINT 2: POST /reset
# PURPOSE: Start a fresh episode
#
# HOW IT WORKS:
#   Agent sends POST request to /reset
#   Optionally sends which task difficulty it wants
#   env.reset() clears everything
#   Returns first bug as Observation
#
# REQUEST BODY (optional):
#   {
#     "task": "easy",   <- or "medium" or "hard" or "all"
#     "seed": 42        <- for reproducible results
#   }
#
# RESPONSE:
#   The first bug report as Observation object
# ================================================================
@app.post("/reset")
async def reset(task: str = "all", seed: int = 42):

    global env

    try:
        # Create new environment with requested settings
        # This allows judges to test specific difficulty levels!
        env = CodeReviewEnv(task=task, seed=seed)

        # Reset and get first observation
        observation = env.reset()

        # Return observation as dict
        return {
            "observation": observation.model_dump(),
            "info": {
                "task": task,
                "seed": seed,
                "total_bugs": len(env.bugs),
                "message": "Episode started successfully!"
            }
        }

    except Exception as e:
        # If anything goes wrong tell the agent what happened
        raise HTTPException(
            status_code=500,
            detail=f"Reset failed: {str(e)}"
        )


# ================================================================
# ENDPOINT 3: POST /step
# PURPOSE: Agent submits action, gets reward and next bug
#
# HOW IT WORKS:
#   Agent reads current bug
#   Agent decides its answer (action)
#   Agent sends POST to /step with its action
#   env.step() grades the action
#   Returns reward + next bug
#
# REQUEST BODY:
#   {
#     "error_line": 1,
#     "error_type": "SyntaxError",
#     "explanation": "...",       <- optional for medium/hard
#     "fixed_code": "...",        <- optional bonus
#     "root_cause": "...",        <- optional for hard
#     "relevant_log_timestamp": "10:21:44",  <- optional hard
#     "is_duplicate": false,      <- optional hard
#     "assigned_team": "..."      <- optional hard
#   }
#
# RESPONSE:
#   StepResult containing reward + next observation
# ================================================================
@app.post("/step")
async def step(action: Action):

    global env

    # Check if episode has been started
    if env is None:
        raise HTTPException(
            status_code=400,
            detail="Environment not initialized. Call /reset first!"
        )

    try:
        # Process the action through environment
        result = env.step(action)

        # Return full step result as dict
        return {
            "observation": result.observation.model_dump() if result.observation else None,
            "reward": result.reward.model_dump(),
            "done": result.done,
            "info": result.info
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Step failed: {str(e)}"
        )


# ================================================================
# ENDPOINT 4: GET /state
# PURPOSE: Return current environment state anytime
#
# HOW IT WORKS:
#   Agent can call this anytime to check progress
#   Returns scoreboard snapshot
#   Does NOT change anything in the environment
#
# RESPONSE:
#   State object with current progress and scores
# ================================================================
@app.get("/state")
async def state():

    global env

    if env is None:
        raise HTTPException(
            status_code=400,
            detail="Environment not initialized. Call /reset first!"
        )

    try:
        current_state = env.state()
        return current_state.model_dump()

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"State failed: {str(e)}"
        )


# ================================================================
# ENDPOINT 5: GET /health
# PURPOSE: Detailed health check for HuggingFace
#
# WHY NEEDED:
#   HuggingFace Space pings /health to verify deployment
#   Returns detailed status including environment info
# ================================================================
@app.get("/health")
async def health():

    global env

    return {
        "status": "healthy",
        "environment_loaded": env is not None,
        "total_bugs": len(env.bugs) if env else 0,
        "is_done": env.is_done if env else False
    }


# ================================================================
# RUN SERVER
# PURPOSE: Start the server when file is run directly
#
# WHY PORT 7860:
#   HuggingFace Spaces uses port 7860 by default!
#   Using any other port = deployment fails!
#
# host="0.0.0.0" means:
#   Accept requests from any IP address
#   Not just localhost!
# ================================================================
if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=7860,
        reload=False
    )