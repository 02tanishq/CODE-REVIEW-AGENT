# ================================================================
# FILE: app/models.py
# PURPOSE: Define the shape of ALL data in our environment
# THINK OF IT AS: The dictionary/rulebook of our project
# Every other file imports from here!
# ================================================================

# BaseModel = the parent class for all our data shapes
# Field = lets us add descriptions and rules to each field
from pydantic import BaseModel, Field

# Optional = this field can be empty (None)
# List = this field contains multiple items
# Dict = this field is key-value pairs like {"key": "value"}
from typing import Optional, List, Dict


# ================================================================
# HELPER MODEL 1: LogEntry
# PURPOSE: One single line from a server/app error log
# USED IN: Hard bugs — agent must find the REAL error
#          among red herrings
# ================================================================
class LogEntry(BaseModel):

    timestamp: str = Field(
        description="When this log entry was recorded",
        # Example: "10:21:44"
    )

    error: str = Field(
        description="The actual log message or error",
        # Example: "UnboundLocalError: kern referenced before assignment"
    )

    relevant: bool = Field(
        description="Is this the real error? (hidden from agent, used by grader only)",
        # True  = this IS the real error
        # False = this is a red herring / unrelated log
    )


# ================================================================
# HELPER MODEL 2: Developer
# PURPOSE: Represents one developer on the team
# USED IN: Hard bugs — agent must assign to right person
#          even if primary expert is OOO (Out of Office)
# ================================================================
class Developer(BaseModel):

    name: str = Field(
        description="Developer's name",
        # Example: "Alice", "Bob", "Carol"
    )

    expertise: List[str] = Field(
        description="What topics this developer specializes in",
        # Example: ["payments", "currency", "gateway"]
    )

    is_available: bool = Field(
        description="Is this developer available right now?",
        # True  = available, can be assigned
        # False = OOO, on leave, in meeting
    )

    fallback: Optional[str] = Field(
        default=None,
        description="Who covers when this developer is unavailable",
        # Example: "Bob" means Bob covers when Alice is OOO
    )


# ================================================================
# HELPER MODEL 3: PreviousBug
# PURPOSE: Summary of a bug that was reported before
# USED IN: Hard bugs — agent must detect semantic duplicates
#          (same bug reported in different words)
# ================================================================
class PreviousBug(BaseModel):

    bug_id: str = Field(
        description="ID of the previously reported bug",
        # Example: "BUG-101"
    )

    title: str = Field(
        description="Title of the previous bug report",
        # Example: "JWT auth token returns 500 error"
    )

    description: str = Field(
        description="Description of the previous bug",
    )

    technical_terms: List[str] = Field(
        description="Technical keywords in this bug report",
        # Example: ["JWT", "auth token", "500 error"]
        # Agent uses these to detect semantic duplicates!
    )

    status: str = Field(
        description="Current status of this previous bug",
        # "open", "resolved", "in_progress"
    )


# ================================================================
# MAIN MODEL 1: Observation
# PURPOSE: What the AI Agent SEES — the bug report shown to agent
# THINK OF IT AS: The question paper given to the agent
# USED IN: reset() returns this, step() returns next one
# ================================================================
class Observation(BaseModel):

    # ---- Basic info about the bug ----
    bug_id: str = Field(
        description="Unique identifier for this bug",
        # Example: "EASY-001", "HARD-005"
    )

    bug_title: str = Field(
        description="Short one-line title of the bug",
        # Example: "Missing colon in function definition"
    )

    bug_description: str = Field(
        description="Full human-readable description of what is wrong",
        # Example: "The function calculate_area is missing a colon..."
    )

    bug_category: str = Field(
        description="Category/type of this bug",
        # Example: "SyntaxError - Missing Colon"
        # Gives agent a hint about what kind of bug to look for
    )

    # ---- The actual broken code ----
    buggy_code: str = Field(
        description="The broken Python code that contains the bug",
        # This is what agent must analyze!
        # Example: "def calculate_area(radius)\n    return 3.14 * radius"
    )

    # ---- Task instructions ----
    task_type: str = Field(
        description="What the agent must do with this bug",
        # "find_error_line"   = Task 1 Easy:   just find line + error type
        # "find_and_explain"  = Task 2 Medium: find + explain + edge cases
        # "full_review"       = Task 3 Hard:   complete analysis
    )

    difficulty: str = Field(
        description="Difficulty level of this bug",
        # "easy", "medium", or "hard"
    )

    # ---- Extra context for hard bugs (optional) ----
    error_logs: Optional[List[LogEntry]] = Field(
        default=None,
        description="Server logs that may contain red herrings. Agent must find the REAL relevant log",
        # Hard bugs have 4 logs but only 1-2 are relevant
        # Agent must identify correct timestamp!
    )

    previous_bugs: Optional[List[PreviousBug]] = Field(
        default=None,
        description="Previously reported bugs. Agent must check if current bug is a duplicate",
        # Used for semantic duplicate detection in hard bugs
    )

    available_developers: Optional[List[Developer]] = Field(
        default=None,
        description="Team members and their availability. Agent must assign to someone who is actually free",
        # Used for OOO assignment in hard bugs
    )

    os_details: Optional[Dict[str, str]] = Field(
        default=None,
        description="OS-specific information about which environments are affected",
        # Example: {"affected": "Windows 10", "not_affected": "Ubuntu 22.04"}
    )


# ================================================================
# MAIN MODEL 2: Action
# PURPOSE: What the AI Agent SUBMITS as its answer
# THINK OF IT AS: The answer sheet the agent fills in
# USED IN: step(action) receives this from agent
# ================================================================
class Action(BaseModel):

    # ---- Required for ALL tasks ----
    error_line: int = Field(
        description="Line number where the bug is located",
        # Example: 1, 2, 3...
        # Agent MUST always provide this
    )

    error_type: str = Field(
        description="The type/category of the bug found",
        # Easy examples:   "SyntaxError", "NameError", "IndexError"
        # Medium examples: "LogicError - Off By One", "Race Condition"
        # Hard examples:   "UnboundLocalError", "SQL Injection"
    )

    # ---- Required for MEDIUM + HARD tasks ----
    wrong_code: Optional[str] = Field(
        default=None,
        description="The exact wrong code snippet that contains the bug",
        # Example: "    return totol"
    )

    fixed_code: Optional[str] = Field(
        default=None,
        description="The corrected version of the buggy code",
        # Example: "    return total"
    )

    explanation: Optional[str] = Field(
        default=None,
        description="Agent's explanation of why this is a bug and how the fix works",
        # Example: "Variable name is misspelled. totol should be total"
    )

    edge_cases: Optional[List[str]] = Field(
        default=None,
        description="Edge cases that this bug affects or that the fix must handle",
        # Example: ["empty list crashes", "negative numbers not handled"]
        # Required for medium difficulty tasks
    )

    # ---- Required for HARD tasks only ----
    root_cause: Optional[str] = Field(
        default=None,
        description="Deep explanation of the ROOT CAUSE of the bug (not just symptoms)",
        # Example: "kern is used on line 2 but Python sees assignment on line 3
        #           so treats it as local throughout function"
    )

    relevant_log_timestamp: Optional[str] = Field(
        default=None,
        description="Timestamp of the REAL error in the logs (not a red herring)",
        # Example: "10:21:44"
        # Agent must correctly identify which log entry is the real one
    )

    # ---- Duplicate detection for HARD tasks ----
    is_duplicate: Optional[bool] = Field(
        default=None,
        description="Is this bug a duplicate of a previously reported bug?",
        # True  = same bug was reported before in different words
        # False = this is a new unique bug
    )

    duplicate_of: Optional[str] = Field(
        default=None,
        description="If duplicate, what is the ID of the original bug report?",
        # Example: "BUG-101"
    )

    duplicate_reasoning: Optional[str] = Field(
        default=None,
        description="Why does agent think this is a duplicate? What semantic connection did it find?",
        # Example: "Login not working is caused by JWT token failure.
        #           Both describe authenticate() calling deleted endpoint"
    )

    # ---- Assignment for HARD tasks ----
    assigned_team: Optional[str] = Field(
        default=None,
        description="Which team should fix this bug",
        # Example: "Auth Team", "Payments Team", "Security Team"
    )

    assigned_developer: Optional[str] = Field(
        default=None,
        description="Specific developer to assign to (must be available!)",
        # Example: "Bob" (not Alice who is OOO)
    )

    fallback_developer: Optional[str] = Field(
        default=None,
        description="Backup developer if primary is unavailable",
    )

    # ---- OS-specific fields for HARD tasks ----
    affected_environments: Optional[List[str]] = Field(
        default=None,
        description="Which OS/environments show this bug",
        # Example: ["Windows 10", "Windows 11"]
    )

    not_affected_environments: Optional[List[str]] = Field(
        default=None,
        description="Which OS/environments do NOT show this bug",
        # Example: ["Ubuntu 22.04", "macOS 13"]
    )


# ================================================================
# MAIN MODEL 3: Reward
# PURPOSE: The score given to agent after checking its answer
# THINK OF IT AS: The marked answer sheet with grades
# USED IN: graders.py creates this, step() returns it
# ================================================================
class Reward(BaseModel):

    score: float = Field(
        description="Total score between 0.0 and 1.0",
        ge=0.0,   # ge = greater than  (minimum value)
        le=1.0    # le = less than  (maximum value)
        
        # 0.5 = partially correct
        
    )

    max_score: float = Field(
        default=0.99,
        description="Maximum possible score for this task",
    )

    feedback: str = Field(
        description="Human-readable explanation of why agent got this score",
        # Example: "Error line correct! Error type wrong. Explanation missing."
        # This helps agent LEARN what it did wrong!
    )

    breakdown: Dict[str, float] = Field(
        default={},
        description="Score breakdown showing points earned for each field",
        # Easy example:
        # {"error_line": 0.5, "error_type": 0.5}
        #
        # Medium example:
        # {"error_line": 0.25, "error_type": 0.25,
        #  "explanation": 0.25, "edge_cases": 0.25}
        #
        # Hard example:
        # {"error_line": 0.15, "error_type": 0.15,
        #  "root_cause": 0.15, "relevant_log": 0.15,
        #  "duplicate": 0.15, "assignment": 0.15,
        #  "fixed_code": 0.10}
    )

    is_correct: bool = Field(
        description="Quick check: did agent get the most important parts right?",
        # True if score >= 0.7 (70% or more correct)
    )


# ================================================================
# MAIN MODEL 4: StepResult
# PURPOSE: Everything returned by step() after agent acts
# THINK OF IT AS: The complete result slip after one exam question
# USED IN: step() returns this to the agent
# ================================================================
class StepResult(BaseModel):

    observation: Optional[Observation] = Field(
        default=None,
        description="The NEXT bug report for agent to analyze",
        # None means there are no more bugs (episode is done!)
    )

    reward: Reward = Field(
        description="Score and feedback for the action just taken",
    )

    done: bool = Field(
        description="Is the entire episode finished?",
        # False = more bugs to review
        # True  = all bugs done, episode complete!
    )

    info: Dict = Field(
        default={},
        description="Extra debug information for developers",
        # Example: {
        #   "correct_answer": {"error_line": 1, "error_type": "SyntaxError"},
        #   "agent_answer":   {"error_line": 2, "error_type": "NameError"},
        #   "bugs_remaining": 7,
        #   "task_number": 1
        # }
    )


# ================================================================
# MAIN MODEL 5: State
# PURPOSE: Current status snapshot of the environment
# THINK OF IT AS: The scoreboard showing current progress
# USED IN: state() returns this anytime agent wants to check
# ================================================================
class State(BaseModel):

    current_task: int = Field(
        description="Which task number agent is currently on (1, 2, or 3)",
        # 1 = Easy task (find_error_line)
        # 2 = Medium task (find_and_explain)
        # 3 = Hard task (full_review)
    )

    current_difficulty: str = Field(
        description="Current difficulty level",
        # "easy", "medium", or "hard"
    )

    bugs_attempted: int = Field(
        description="How many bugs the agent has tried to review so far",
    )

    bugs_remaining: int = Field(
        description="How many bugs are still left to review",
    )

    total_bugs: int = Field(
        description="Total number of bugs in this episode",
    )

    total_score: float = Field(
        description="Total score accumulated across all bugs reviewed so far",
    )

    max_possible_score: float = Field(
        description="Maximum score achievable if all remaining bugs answered perfectly",
    )

    score_percentage: float = Field(
        description="Current score as a percentage (0.0 to 100.0)",
        # Example: 75.5 means agent has scored 75.5% so far
    )

    task_scores: Dict[str, float] = Field(
        default={},
        description="Score breakdown by task type",
        # Example: {
        #   "easy":   0.9,   <- agent doing well on easy bugs
        #   "medium": 0.6,   <- struggling a bit on medium
        #   "hard":   0.3    <- really struggling on hard!
        # }
    )

    is_done: bool = Field(
        description="Has the agent finished all bugs in this episode?",
    )

    current_bug_id: Optional[str] = Field(
        default=None,
        description="ID of the bug currently being reviewed",
        # None if episode is finished
    )