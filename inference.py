# ================================================================
# FILE: inference.py
# PURPOSE: Baseline inference script that runs an AI agent
#          through our Code Review Agent environment
#
# THIS FILE IS MANDATORY FOR SUBMISSION!
#
# WHAT IT DOES:
#   1. Starts our FastAPI environment server
#   2. Connects to real LLM using OpenAI client
#   3. Runs agent through all 3 task difficulties
#   4. Prints scores in required [START][STEP][END] format
#   5. Shows reproducible final scores
#
# HOW JUDGES USE IT:
#   They run: python3 inference.py
#   They see scores printed in standard format
#   They verify environment works end to end
#
# MANDATORY ENV VARIABLES:
#   API_BASE_URL = LLM API endpoint
#   MODEL_NAME   = which model to use
#   HF_TOKEN     = HuggingFace/API key
# ================================================================

import os
import json
import time
import requests
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

API_BASE_URL = os.getenv(
    "API_BASE_URL",
    "https://api.groq.com/openai/v1"
)
MODEL_NAME = os.getenv("MODEL_NAME", "llama-3.1-8b-instant")
HF_TOKEN = os.getenv("HF_TOKEN", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
ENV_URL = os.getenv("ENV_URL", "http://localhost:7860")

API_KEY = GROQ_API_KEY if GROQ_API_KEY else HF_TOKEN

if not API_KEY:
    print("ERROR: No API key found!")
    print("Copy .env.example to .env and add your tokens")
    exit(1)
# ================================================================
# OPENAI CLIENT SETUP
# Using OpenAI client as REQUIRED by hackathon rules
# API_BASE_URL lets us point to any OpenAI compatible API
# ================================================================
client = OpenAI(
    base_url=API_BASE_URL,
    api_key=API_KEY
)

# ================================================================
# HELPER FUNCTION 1: call_env()
# PURPOSE: Make HTTP requests to our FastAPI environment
#
# WHY SEPARATE FUNCTION:
#   Cleaner code
#   Error handling in one place
#   Easy to change URL if needed
# ================================================================
def call_env(endpoint: str, method: str = "GET",
             data: dict = None) -> dict:

    url = f"{ENV_URL}{endpoint}"

    try:
        if method == "POST":
            response = requests.post(url, json=data, timeout=30)
        else:
            response = requests.get(url, timeout=30)

        response.raise_for_status()
        return response.json()

    except requests.exceptions.ConnectionError:
        print(f"ERROR: Cannot connect to environment at {url}")
        print("Make sure server is running!")
        raise

    except Exception as e:
        print(f"ERROR calling {endpoint}: {str(e)}")
        raise


# ================================================================
# HELPER FUNCTION 2: build_prompt()
# PURPOSE: Convert bug observation into LLM prompt
#
# WHY THIS MATTERS:
#   How you ask the LLM affects quality of answers
#   Good prompt = better agent performance
#   This is the "baseline" — not optimized on purpose
#   So there is room for improvement!
# ================================================================
def build_prompt(observation: dict) -> str:

    difficulty = observation.get("difficulty", "easy")
    task_type = observation.get("task_type", "find_error_line")
    bug_title = observation.get("bug_title", "")
    bug_description = observation.get("bug_description", "")
    bug_category = observation.get("bug_category", "")
    buggy_code = observation.get("buggy_code", "")

    # Base prompt — always included
    prompt = f"""You are an expert code reviewer.
Analyze the following bug report and answer in JSON format only.

Bug Title: {bug_title}
Bug Category: {bug_category}
Bug Description: {bug_description}

Buggy Code:
{buggy_code}
"""

    # Add log entries if present (hard bugs)
    if observation.get("error_logs"):
        prompt += "\nError Logs (one is relevant, others are red herrings):\n"
        for log in observation["error_logs"]:
            prompt += f"  [{log['timestamp']}] {log['error']}\n"

    # Add previous bugs if present (duplicate detection)
    if observation.get("previous_bugs"):
        prompt += "\nPreviously Reported Bugs:\n"
        for pb in observation["previous_bugs"]:
            prompt += f"  ID: {pb['bug_id']} | Title: {pb['title']}\n"
            prompt += f"  Description: {pb['description']}\n"

    # Add developer availability if present (OOO assignment)
    if observation.get("available_developers"):
        prompt += "\nAvailable Developers:\n"
        for dev in observation["available_developers"]:
            status = "AVAILABLE" if dev["is_available"] else "OUT OF OFFICE"
            prompt += f"  {dev['name']}: {status} | Skills: {dev['expertise']}\n"
            if dev.get("fallback"):
                prompt += f"    Fallback: {dev['fallback']}\n"

    # Add OS details if present
    if observation.get("os_details"):
        prompt += f"\nOS Details: {observation['os_details']}\n"

    # Task specific instructions
    if task_type == "find_error_line":
        prompt += """
Task: Find the bug and respond with JSON:
{
  "error_line": <line number where bug is>,
  "error_type": <type of error>,
  "fixed_code": <corrected code>
}"""

    elif task_type == "find_and_explain":
        prompt += """
Task: Find and explain the bug. Respond with JSON:
{
  "error_line": <line number>,
  "error_type": <error type>,
  "explanation": <why this is a bug>,
  "edge_cases": [<list of edge cases affected>],
  "fixed_code": <corrected code>
}"""

    else:
        # full_review for hard bugs
        prompt += """
Task: Complete code review. Respond with JSON:
{
  "error_line": <line number>,
  "error_type": <error type>,
  "root_cause": <deep explanation of why bug exists>,
  "relevant_log_timestamp": <timestamp of real error log>,
  "is_duplicate": <true or false>,
  "duplicate_of": <bug ID if duplicate, else null>,
  "assigned_team": <which team should fix this>,
  "assigned_developer": <specific developer if available>,
  "fixed_code": <corrected code>
}"""

    prompt += "\n\nRespond ONLY with valid JSON. No extra text."

    return prompt


# ================================================================
# HELPER FUNCTION 3: ask_llm()
# PURPOSE: Send prompt to LLM and get structured response
#
# WHY TRY/EXCEPT:
#   LLM might return invalid JSON
#   API might fail temporarily
#   We handle errors gracefully instead of crashing
# ================================================================
def ask_llm(prompt: str) -> dict:

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": "You are a code reviewer. Respond with ONLY a JSON object. No other text. Start your response with { and end with }."
                },
                {
                    "role": "user",
                    "content": prompt + "\n\nIMPORTANT: Your entire response must be a single JSON object starting with { and ending with }. No markdown, no backticks, no explanation text."
                }
            ],
            max_tokens=1000,
            temperature=0.1
            # Low temperature = more consistent/deterministic answers
            # Important for reproducible scores!
        )

        # Extract text response
        text = response.choices[0].message.content.strip()

        # Remove markdown code blocks if LLM added them
        # Some models wrap JSON in ```json ... ```
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        text = text.strip()

        # Parse JSON response
        return json.loads(text)

    except json.JSONDecodeError:
        # LLM returned invalid JSON
        # Return a minimal valid action so episode continues
        print("WARNING: LLM returned invalid JSON, using default action")
        return {
            "error_line": 1,
            "error_type": "SyntaxError"
        }

    except Exception as e:
        print(f"WARNING: LLM call failed: {str(e)}")
        return {
            "error_line": 1,
            "error_type": "SyntaxError"
        }


# ================================================================
# HELPER FUNCTION 4: parse_llm_response()
# PURPOSE: Convert LLM JSON response into Action format
#
# WHY NEEDED:
#   LLM might use different key names
#   Some fields might be missing
#   We normalize everything to match Action model
# ================================================================
def parse_llm_response(response: dict) -> dict:

    action = {}

    # Force error_line to be integer always
    try:
        action["error_line"] = int(response.get("error_line", 1))
    except (ValueError, TypeError):
        action["error_line"] = 1

    # Force error_type to be string always
    try:
        action["error_type"] = str(response.get("error_type", "SyntaxError"))
    except (ValueError, TypeError):
        action["error_type"] = "SyntaxError"

    # Optional string fields
    string_fields = [
        "explanation",
        "fixed_code",
        "root_cause",
        "relevant_log_timestamp",
        "duplicate_of",
        "duplicate_reasoning",
        "assigned_team",
        "assigned_developer",
        "fallback_developer"
    ]

    for field in string_fields:
        val = response.get(field)
        if val is not None:
            action[field] = str(val)

    # Optional list fields
    list_fields = [
        "edge_cases",
        "affected_environments",
        "not_affected_environments"
    ]

    for field in list_fields:
        val = response.get(field)
        if val is not None and isinstance(val, list):
            action[field] = val

    # Optional boolean fields
    bool_fields = ["is_duplicate"]

    for field in bool_fields:
        val = response.get(field)
        if val is not None:
            if isinstance(val, bool):
                action[field] = val
            elif isinstance(val, str):
                action[field] = val.lower() == "true"

    return action

# ================================================================
# MAIN FUNCTION: run_episode()
# PURPOSE: Run one complete episode through the environment
#
# PRINTS MANDATORY LOG FORMAT:
#   [START] = episode beginning info
#   [STEP]  = each action and reward
#   [END]   = final scores
#
# ANY DEVIATION FROM THIS FORMAT = incorrect evaluation scoring!
# ================================================================
def run_episode(task: str = "all", seed: int = 42) -> dict:

    episode_scores = []
    step_count = 0

    # ---- MANDATORY [START] LOG ----
    start_info = {
        "task": task,
        "seed": seed,
        "model": MODEL_NAME,
        "env_url": ENV_URL
    }
    print(f"[START] {json.dumps(start_info)}")

    # Step 1: Reset environment
    reset_response = call_env(
        "/reset",
        method="POST",
        data={"task": task, "seed": seed}
    )

    observation = reset_response.get("observation")

    if not observation:
        print("[END] " + json.dumps({"error": "Reset failed"}))
        return {}

    # Step 2: Run episode loop
    # Continue until environment says done=True
    while observation and step_count < 100:
        # Safety limit of 100 steps prevents infinite loops

        step_count += 1
        bug_id = observation.get("bug_id", "unknown")

        # Build prompt from observation
        prompt = build_prompt(observation)

        llm_response = ask_llm(prompt)

        if llm_response is None:
            print(f"Skipping bug {bug_id} - LLM failed")
    # Move to next bug manually
            step_response = call_env(
                "/step",
                method="POST",
                data={"error_line": 99, "error_type": "Unknown"}
            )
            reward = step_response.get("reward", {})
            score = reward.get("score", 0.0)
            done = step_response.get("done", True)
            observation = step_response.get("observation")
            episode_scores.append(0.0)
            continue

        action = parse_llm_response(llm_response)

        # Send action to environment
        try:
            step_response = call_env(
                "/step",
                method="POST",
                data=action
            )
        except Exception as e:
            print(f"Step failed: {e}")
            print(f"Action that caused error: {action}")
            break

        # Extract reward and next observation
        reward = step_response.get("reward", {})
        score = reward.get("score", 0.0)
        done = step_response.get("done", True)
        observation = step_response.get("observation")

        episode_scores.append(score)

        # ---- MANDATORY [STEP] LOG ----
        step_info = {
            "step": step_count,
            "bug_id": bug_id,
            "action": action,
            "score": score,
            "feedback": reward.get("feedback", ""),
            "done": done
        }
        print(f"[STEP] {json.dumps(step_info)}")

        # Small delay to avoid hitting API rate limits
        time.sleep(0.5)

        if done:
            break

    # Calculate final statistics
    final_score = (
        sum(episode_scores) / len(episode_scores)
        if episode_scores else 0.0
    )

    # ---- MANDATORY [END] LOG ----
    end_info = {
        "total_steps": step_count,
        "total_score": round(sum(episode_scores), 2),
        "average_score": round(final_score, 2),
        "scores_per_step": [round(s, 2) for s in episode_scores],
        "task": task,
        "model": MODEL_NAME
    }
    print(f"[END] {json.dumps(end_info)}")

    return end_info


# ================================================================
# ENTRY POINT
# PURPOSE: Run baseline when script is called directly
#
# RUNS 3 EPISODES:
#   Episode 1: Easy bugs only
#   Episode 2: Medium bugs only
#   Episode 3: Hard bugs only
#
# This shows judges how agent performs at each difficulty!
# ================================================================
if __name__ == "__main__":

    print("=" * 60)
    print("Code Review Agent — Baseline Inference")
    print("=" * 60)
    print(f"Model: {MODEL_NAME}")
    print(f"Environment: {ENV_URL}")
    print("=" * 60)

    results = {}

    # Run easy episode
    print("\n--- TASK 1: EASY BUGS ---")
    results["easy"] = run_episode(task="easy", seed=42)

    # Small pause between episodes
    time.sleep(1)

    # Run medium episode
    print("\n--- TASK 2: MEDIUM BUGS ---")
    results["medium"] = run_episode(task="medium", seed=42)

    time.sleep(1)

    # Run hard episode
    print("\n--- TASK 3: HARD BUGS ---")
    results["hard"] = run_episode(task="hard", seed=42)

    # Final summary
    print("\n" + "=" * 60)
    print("FINAL RESULTS SUMMARY")
    print("=" * 60)

    for task, result in results.items():
        if result:
            avg = result.get("average_score", 0)
            steps = result.get("total_steps", 0)
            print(f"{task.upper():10} | "
                  f"Steps: {steps:3} | "
                  f"Avg Score: {avg:.2f}")

    print("=" * 60)
    print("Baseline inference complete!")