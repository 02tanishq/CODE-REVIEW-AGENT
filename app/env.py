# ================================================================
# FILE: app/env.py
# PURPOSE: The core environment logic
#
# THINK OF IT AS: The exam hall manager
#   reset() = "Everyone sit down, here is first question"
#   step()  = "Check answer, give marks, next question"
#   state() = "Here is current scoreboard"
#
# THIS FILE connects everything together:
#   reads bugs from bugs.json
#   uses models.py for data shapes
#   uses graders.py for scoring
# ================================================================

import json
import random
from pathlib import Path

from app.models import (
    Observation,
    Action,
    StepResult,
    State,
    LogEntry,
    Developer,
    PreviousBug
)
from app.graders import grade

class CodeReviewEnv:

    # ============================================================
    # __init__() — runs once when environment is created
    # PURPOSE: Load all bugs and set up initial state
    # THINK OF IT AS: Setting up the exam hall before students arrive
    # ============================================================
    def __init__(self, task: str = "easy", seed: int = 42):

        # task controls which difficulty we run
        # "easy"   = Task 1 (find error line + type)
        # "medium" = Task 2 (find + explain + edge cases)
        # "hard"   = Task 3 (full review)
        # "all"    = all difficulties mixed together
        self.task = task

        # seed makes randomness reproducible
        # same seed = same order of bugs every time
        # judges need this for reproducible scores!
        self.seed = seed
        random.seed(seed)

        # Load bugs from JSON file
        # Path(__file__) gets location of this file
        # .parent goes up to app/ folder
        data_path = Path(__file__).parent / "data" / "bugs.json"
        with open(data_path, "r") as f:
            all_bugs = json.load(f)["bugs"]

        # Filter bugs based on task difficulty
        if task == "all":
            self.bugs = all_bugs
        else:
            self.bugs = [
                b for b in all_bugs
                if b["difficulty"] == task
            ]

        # Shuffle bugs so order is random but reproducible
        random.shuffle(self.bugs)

        # Internal state variables
        # These track where we are in the episode
        self.current_index = 0        # which bug we are on
        self.total_score = 0.0        # accumulated score
        self.bugs_attempted = 0       # how many bugs tried
        self.is_done = False          # is episode finished
        self.task_scores = {          # score per difficulty
            "easy": [],
            "medium": [],
            "hard": []
        }

    # ============================================================
    # reset() — start a fresh episode
    # PURPOSE: Clear everything and return first bug
    # CALLED BY: Agent at start of every new episode
    # RETURNS: Observation (first bug report)
    # ============================================================
    def reset(self) -> Observation:

        # Reset random seed for reproducibility
        random.seed(self.seed)
        random.shuffle(self.bugs)

        # Reset all tracking variables to zero
        self.current_index = 0
        self.total_score = 0.0
        self.bugs_attempted = 0
        self.is_done = False
        self.task_scores = {
            "easy": [],
            "medium": [],
            "hard": []
        }

        # Return the first bug as an Observation
        return self._make_observation(self.bugs[0])

    # ============================================================
    # step() — process agent's action and return result
    # PURPOSE: Check answer, give reward, return next bug
    # CALLED BY: Agent after it analyzes each bug
    # RECEIVES: Action (agent's answer)
    # RETURNS: StepResult (reward + next observation)
    # ============================================================
    def step(self, action: Action) -> StepResult:

        # Safety check: if episode already done
        # agent should have called reset() first!
        if self.is_done:
            from app.models import Reward
            return StepResult(
                observation=None,
                reward=Reward(
                    score=0.0,
                    max_score=1.0,
                    feedback="Episode is done. Call reset() to start again.",
                    breakdown={},
                    is_correct=False
                ),
                done=True,
                info={"error": "Episode already finished"}
            )

        # Get the current bug agent is answering
        current_bug = self.bugs[self.current_index]

        # Grade the agent's action against correct answer
        # grade() automatically picks right grader
        # based on bug difficulty (easy/medium/hard)
        reward = grade(action, current_bug)

        # Update tracking variables
        self.total_score += reward.score
        self.bugs_attempted += 1

        # Track score per difficulty level
        difficulty = current_bug["difficulty"]
        self.task_scores[difficulty].append(reward.score)

        # Move to next bug
        self.current_index += 1

        # Check if we have finished all bugs
        if self.current_index >= len(self.bugs):
            # Episode is complete!
            self.is_done = True

            return StepResult(
                observation=None,    # no more bugs
                reward=reward,       # reward for last bug
                done=True,
                info={
                    "message": "Episode complete!",
                    "total_score": self.total_score,
                    "bugs_attempted": self.bugs_attempted,
                    "final_score": round(
                        self.total_score / self.bugs_attempted, 2
                    ),
                    "correct_answer": current_bug["correct_answer"]
                }
            )

        # Episode not done yet — return next bug
        next_bug = self.bugs[self.current_index]

        return StepResult(
            observation=self._make_observation(next_bug),
            reward=reward,
            done=False,
            info={
                "correct_answer": current_bug["correct_answer"],
                "bugs_remaining": len(self.bugs) - self.current_index,
                "current_score": round(self.total_score, 2)
            }
        )

    # ============================================================
    # state() — return current environment status
    # PURPOSE: Let agent check its progress anytime
    # CALLED BY: Agent whenever it wants a status update
    # RETURNS: State (scoreboard snapshot)
    # ============================================================
    def state(self) -> State:

        # Calculate score percentage
        if self.bugs_attempted > 0:
            score_pct = round(
                (self.total_score / self.bugs_attempted) * 100, 1
            )
        else:
            score_pct = 0.0

        # Calculate average score per difficulty level
        task_avg = {}
        for difficulty, scores in self.task_scores.items():
            if scores:
                task_avg[difficulty] = round(
                    sum(scores) / len(scores), 2
                )

        # Current bug info
        if not self.is_done and self.current_index < len(self.bugs):
            current_bug = self.bugs[self.current_index]
            current_bug_id = current_bug["bug_id"]
            current_difficulty = current_bug["difficulty"]
        else:
            current_bug_id = None
            current_difficulty = self.task

        # Map difficulty to task number
        task_number_map = {
            "easy": 1,
            "medium": 2,
            "hard": 3,
            "all": 1
        }

        return State(
            current_task=task_number_map.get(
                current_difficulty, 1
            ),
            current_difficulty=current_difficulty,
            bugs_attempted=self.bugs_attempted,
            bugs_remaining=len(self.bugs) - self.current_index,
            total_bugs=len(self.bugs),
            total_score=round(self.total_score, 2),
            max_possible_score=float(len(self.bugs)),
            score_percentage=score_pct,
            task_scores=task_avg,
            is_done=self.is_done,
            current_bug_id=current_bug_id
        )

    # ============================================================
    # _make_observation() — private helper method
    # PURPOSE: Convert raw bug dict into Observation model
    # WHY PRIVATE: Only used internally, not called by agent
    # NOTE: Methods starting with _ are private by convention
    # ============================================================
    def _make_observation(self, bug: dict) -> Observation:

        # Handle optional log entries for hard bugs
        error_logs = None
        if "error_logs" in bug and bug["error_logs"]:
            error_logs = [
                LogEntry(
                    timestamp=log["timestamp"],
                    error=log["error"],
                    relevant=log["relevant"]
                )
                for log in bug["error_logs"]
            ]

        # Handle optional previous bugs for duplicate detection
        previous_bugs = None
        if "previous_bugs" in bug and bug["previous_bugs"]:
            previous_bugs = [
                PreviousBug(
                    bug_id=pb["bug_id"],
                    title=pb["title"],
                    description=pb["description"],
                    technical_terms=pb["technical_terms"],
                    status=pb["status"]
                )
                for pb in bug["previous_bugs"]
            ]

        # Handle optional developer list for OOO assignment
        available_developers = None
        if "available_developers" in bug and bug["available_developers"]:
            available_developers = [
                Developer(
                    name=dev["name"],
                    expertise=dev["expertise"],
                    is_available=dev["is_available"],
                    fallback=dev.get("fallback")
                )
                for dev in bug["available_developers"]
            ]

        # Handle optional OS details
        os_details = bug.get("os_details", None)

        # Build and return the Observation
        return Observation(
            bug_id=bug["bug_id"],
            bug_title=bug["bug_title"],
            bug_description=bug["bug_description"],
            bug_category=bug["bug_category"],
            buggy_code=bug["buggy_code"],
            task_type=bug["task_type"],
            difficulty=bug["difficulty"],
            error_logs=error_logs,
            previous_bugs=previous_bugs,
            available_developers=available_developers,
            os_details=os_details
        )