# ================================================================
# FILE: app/graders.py
# PURPOSE: Score the AI agent's answers for all 3 task types
# KEY FIX: All scores strictly between 0.01 and 0.99
#          Never exactly 0.0 or 1.0!
# ================================================================

from app.models import Action, Reward
import difflib


VALID_ERROR_TYPES = {
    "syntaxerror", "indentationerror", "nameerror",
    "typeerror", "indexerror", "attributeerror",
    "zerodivisionerror", "unboundlocalerror", "keyerror",
    "recursionerror", "valueerror", "importerror",
    "logicerror", "encodingerror", "racecondition",
    "memoryleak", "securityerror", "asyncerror",
    "oserror", "filenotfounderror"
}


def clamp(score: float) -> float:
    """
    PURPOSE: Make sure score is STRICTLY between 0 and 1
    Never exactly 0.0 or 1.0!
    This is required by OpenEnv validation!

    0.0  -> 0.01
    1.0  -> 0.99
    0.5  -> 0.5 (unchanged)
    """
    return round(max(0.01, min(0.99, score)), 2)


def text_similarity(text1: str, text2: str) -> float:
    if not text1 or not text2:
        return 0.0
    t1 = text1.lower().strip()
    t2 = text2.lower().strip()
    return difflib.SequenceMatcher(None, t1, t2).ratio()


def check_error_line(agent_line: int,
                     correct_line: int) -> float:
    if agent_line == correct_line:
        return 0.98      # exact match but not 1.0!
    elif abs(agent_line - correct_line) == 1:
        return 0.5
    else:
        return 0.02      # wrong but not 0.0!


def check_error_type(agent_type: str,
                     correct_type: str) -> float:
    if not agent_type:
        return 0.02

    agent_clean = agent_type.lower().strip()
    correct_clean = correct_type.lower().strip()

    if agent_clean == correct_clean:
        return 0.98

    agent_core = agent_clean.split("-")[0].strip().replace(" ", "")
    correct_core = correct_clean.split("-")[0].strip().replace(" ", "")

    if agent_core == correct_core:
        return 0.7

    if agent_core not in VALID_ERROR_TYPES:
        return 0.02

    similarity = difflib.SequenceMatcher(
        None, agent_clean, correct_clean
    ).ratio()

    if similarity >= 0.7:
        return 0.5

    return 0.02


def check_explanation(agent_explanation: str,
                       correct_explanation: str) -> float:
    if not agent_explanation:
        return 0.02

    similarity = text_similarity(
        agent_explanation,
        correct_explanation
    )

    if similarity >= 0.6:
        return 0.95
    elif similarity >= 0.35:
        return 0.5
    else:
        return 0.02


def check_edge_cases(agent_cases: list,
                      correct_cases: list) -> float:
    if not correct_cases:
        return 0.95

    if not agent_cases:
        return 0.02

    matched = 0
    for correct_case in correct_cases:
        for agent_case in agent_cases:
            similarity = text_similarity(agent_case, correct_case)
            if similarity >= 0.4:
                matched += 1
                break

    raw = matched / len(correct_cases)
    # Make sure not exactly 0 or 1
    return max(0.02, min(0.95, round(raw, 2)))


def check_fixed_code(agent_fix: str,
                      correct_fix: str) -> float:
    if not agent_fix:
        return 0.02

    similarity = text_similarity(agent_fix, correct_fix)

    if similarity >= 0.65:
        return 0.95
    elif similarity >= 0.40:
        return 0.5
    else:
        return 0.02


def run_tests_on_fix(fixed_code: str,
                      test_cases: list) -> float:
    import subprocess
    import tempfile
    import os

    if not fixed_code or not test_cases:
        return 0.02

    passed = 0
    total = len(test_cases)

    for test in test_cases:
        full_code = fixed_code + "\n\n" + test
        tmp_path = None

        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".py",
                delete=False
            ) as tmp:
                tmp.write(full_code)
                tmp_path = tmp.name

            result = subprocess.run(
                ["python3", tmp_path],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                passed += 1

        except subprocess.TimeoutExpired:
            pass
        except Exception:
            pass
        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass

    raw = passed / total if total > 0 else 0.0
    return max(0.02, min(0.95, round(raw, 2)))


# ================================================================
# GRADER 1: grade_easy()
# SCORING:
#   error_line   -> 0.5
#   error_type   -> 0.4
#   tests_passed -> 0.1 (bonus)
# ================================================================
def grade_easy(action: Action, bug: dict) -> Reward:

    correct_answer = bug["correct_answer"]
    test_cases = bug.get("test_cases", [])

    breakdown = {}
    feedback_parts = []

    # CHECK 1: Error Line (worth 0.5)
    line_score = check_error_line(
        action.error_line,
        correct_answer["error_line"]
    )
    breakdown["error_line"] = round(line_score * 0.5, 2)

    if line_score >= 0.9:
        feedback_parts.append(
            f"Line {action.error_line} is correct!"
        )
    elif line_score >= 0.4:
        feedback_parts.append(
            f"Line {action.error_line} is close "
            f"(correct is line {correct_answer['error_line']})"
        )
    else:
        feedback_parts.append(
            f"Wrong line. Error is on line "
            f"{correct_answer['error_line']}"
        )

    # CHECK 2: Error Type (worth 0.4)
    type_score = check_error_type(
        action.error_type,
        correct_answer["error_type"]
    )
    breakdown["error_type"] = round(type_score * 0.4, 2)

    if type_score >= 0.9:
        feedback_parts.append(
            f"Error type correct!"
        )
    elif type_score >= 0.4:
        feedback_parts.append(
            f"Error type partially correct. "
            f"Expected: '{correct_answer['error_type']}'"
        )
    else:
        feedback_parts.append(
            f"Wrong error type. "
            f"Expected: '{correct_answer['error_type']}'"
        )

    # CHECK 3: Test Cases (bonus worth 0.1)
    if test_cases and action.fixed_code:
        test_score = run_tests_on_fix(
            action.fixed_code,
            test_cases
        )
        breakdown["tests_passed"] = round(test_score * 0.1, 2)
        passed_count = int(test_score * len(test_cases))
        feedback_parts.append(
            f"Tests: {passed_count}/{len(test_cases)} passed"
        )

    # CALCULATE TOTAL — clamp strictly between 0.01 and 0.99
    total_score = clamp(sum(breakdown.values()))
    feedback = " | ".join(feedback_parts)
    feedback += f" | Total: {total_score}/1.0"

    return Reward(
        score=total_score,
        max_score=0.99,
        feedback=feedback,
        breakdown=breakdown,
        is_correct=total_score >= 0.6
    )


# ================================================================
# GRADER 2: grade_medium()
# SCORING:
#   error_line   -> 0.25
#   error_type   -> 0.25
#   explanation  -> 0.25
#   edge_cases   -> 0.25
#   tests_passed -> 0.1 (bonus)
# ================================================================
def grade_medium(action: Action, bug: dict) -> Reward:

    correct_answer = bug["correct_answer"]
    test_cases = bug.get("test_cases", [])

    breakdown = {}
    feedback_parts = []

    # CHECK 1: Error Line (worth 0.25)
    line_score = check_error_line(
        action.error_line,
        correct_answer["error_line"]
    )
    breakdown["error_line"] = round(line_score * 0.25, 2)

    if line_score >= 0.9:
        feedback_parts.append("Line correct!")
    elif line_score >= 0.4:
        feedback_parts.append(
            f"Line close "
            f"(expected {correct_answer['error_line']})"
        )
    else:
        feedback_parts.append(
            f"Wrong line "
            f"(expected {correct_answer['error_line']})"
        )

    # CHECK 2: Error Type (worth 0.25)
    type_score = check_error_type(
        action.error_type,
        correct_answer["error_type"]
    )
    breakdown["error_type"] = round(type_score * 0.25, 2)

    if type_score >= 0.9:
        feedback_parts.append("Error type correct!")
    elif type_score >= 0.4:
        feedback_parts.append(
            f"Error type partially correct "
            f"(expected '{correct_answer['error_type']}')"
        )
    else:
        feedback_parts.append(
            f"Wrong error type "
            f"(expected '{correct_answer['error_type']}')"
        )

    # CHECK 3: Explanation (worth 0.25)
    if action.explanation:
        explanation_score = check_explanation(
            action.explanation,
            correct_answer["explanation"]
        )
    else:
        explanation_score = 0.02

    breakdown["explanation"] = round(
        explanation_score * 0.25, 2
    )

    if explanation_score >= 0.9:
        feedback_parts.append("Explanation correct!")
    elif explanation_score >= 0.4:
        feedback_parts.append("Explanation partially correct")
    else:
        feedback_parts.append(
            "Explanation missing or incorrect."
        )

    # CHECK 4: Edge Cases (worth 0.25)
    correct_edge_cases = correct_answer.get("edge_cases", [])

    if action.edge_cases:
        edge_score = check_edge_cases(
            action.edge_cases,
            correct_edge_cases
        )
    else:
        edge_score = 0.02

    breakdown["edge_cases"] = round(edge_score * 0.25, 2)

    if edge_score >= 0.8:
        feedback_parts.append("Edge cases well identified!")
    elif edge_score >= 0.4:
        feedback_parts.append("Some edge cases found")
    else:
        feedback_parts.append("Edge cases missing")

    # CHECK 5: Test Cases (bonus worth 0.1)
    if test_cases and action.fixed_code:
        test_score = run_tests_on_fix(
            action.fixed_code,
            test_cases
        )
        breakdown["tests_passed"] = round(test_score * 0.1, 2)
        passed_count = int(test_score * len(test_cases))
        feedback_parts.append(
            f"Tests: {passed_count}/{len(test_cases)} passed"
        )

    # CALCULATE TOTAL — clamp strictly between 0.01 and 0.99
    total_score = clamp(sum(breakdown.values()))
    feedback = " | ".join(feedback_parts)
    feedback += f" | Total: {total_score}/1.0"

    return Reward(
        score=total_score,
        max_score=0.99,
        feedback=feedback,
        breakdown=breakdown,
        is_correct=total_score >= 0.6
    )


# ================================================================
# GRADER 3: grade_hard()
# SCORING:
#   error_line       -> 0.10
#   error_type       -> 0.10
#   root_cause       -> 0.20
#   relevant_log     -> 0.20
#   duplicate_check  -> 0.20
#   assignment       -> 0.15
#   fixed_code       -> 0.05
#   tests_passed     -> 0.10 (bonus)
# ================================================================
def grade_hard(action: Action, bug: dict) -> Reward:

    correct_answer = bug["correct_answer"]
    test_cases = bug.get("test_cases", [])

    breakdown = {}
    feedback_parts = []

    # CHECK 1: Error Line (worth 0.10)
    line_score = check_error_line(
        action.error_line,
        correct_answer["error_line"]
    )
    breakdown["error_line"] = round(line_score * 0.10, 2)

    if line_score >= 0.9:
        feedback_parts.append("Line correct!")
    elif line_score >= 0.4:
        feedback_parts.append(
            f"Line close "
            f"(expected {correct_answer['error_line']})"
        )
    else:
        feedback_parts.append(
            f"Wrong line "
            f"(expected {correct_answer['error_line']})"
        )

    # CHECK 2: Error Type (worth 0.10)
    type_score = check_error_type(
        action.error_type,
        correct_answer["error_type"]
    )
    breakdown["error_type"] = round(type_score * 0.10, 2)

    if type_score >= 0.9:
        feedback_parts.append("Error type correct!")
    elif type_score >= 0.4:
        feedback_parts.append("Error type partially correct")
    else:
        feedback_parts.append(
            f"Wrong error type "
            f"(expected '{correct_answer['error_type']}')"
        )

    # CHECK 3: Root Cause (worth 0.20)
    if action.root_cause:
        root_score = check_explanation(
            action.root_cause,
            correct_answer["root_cause"]
        )
    else:
        root_score = 0.02

    breakdown["root_cause"] = round(root_score * 0.20, 2)

    if root_score >= 0.9:
        feedback_parts.append("Root cause analysis correct!")
    elif root_score >= 0.4:
        feedback_parts.append("Root cause partially correct")
    else:
        feedback_parts.append("Root cause missing or wrong")

    # CHECK 4: Relevant Log Timestamp (worth 0.20)
    correct_timestamp = correct_answer.get(
        "relevant_log_timestamp"
    )

    if correct_timestamp:
        if action.relevant_log_timestamp:
            if (action.relevant_log_timestamp.strip() ==
                    correct_timestamp.strip()):
                log_score = 0.98
                feedback_parts.append(
                    f"Correct log identified!"
                )
            else:
                log_score = 0.02
                feedback_parts.append(
                    f"Wrong log picked "
                    f"(correct: {correct_timestamp})"
                )
        else:
            log_score = 0.02
            feedback_parts.append(
                f"No log identified "
                f"(correct: {correct_timestamp})"
            )
    else:
        log_score = 0.95
        feedback_parts.append("No log check needed")

    breakdown["relevant_log"] = round(log_score * 0.20, 2)

    # CHECK 5: Duplicate Detection (worth 0.20)
    correct_is_dup = correct_answer.get("is_duplicate", False)

    if action.is_duplicate is not None:
        if action.is_duplicate == correct_is_dup:
            dup_score = 0.7

            if correct_is_dup and action.duplicate_of:
                if (action.duplicate_of ==
                        correct_answer.get("duplicate_of")):
                    dup_score = 0.98
                    feedback_parts.append(
                        f"Duplicate correctly identified!"
                    )
                else:
                    dup_score = 0.5
                    feedback_parts.append(
                        "Duplicate detected but wrong ID"
                    )
            elif not correct_is_dup:
                feedback_parts.append(
                    "Correctly identified as non-duplicate!"
                )
        else:
            dup_score = 0.02
            if correct_is_dup:
                feedback_parts.append(
                    "Missed! This IS a duplicate"
                )
            else:
                feedback_parts.append(
                    "Wrong! This is NOT a duplicate"
                )
    else:
        dup_score = 0.02
        feedback_parts.append("Duplicate check missing")

    breakdown["duplicate_check"] = round(dup_score * 0.20, 2)

    # CHECK 6: Developer Assignment (worth 0.15)
    correct_dev = correct_answer.get("assigned_developer")
    correct_team = correct_answer.get("assigned_team")

    assign_score = 0.02

    if correct_dev:
        if action.assigned_developer:
            if action.assigned_developer == correct_dev:
                assign_score = 0.98
                feedback_parts.append(
                    f"Correctly assigned to {correct_dev}!"
                )
            else:
                assign_score = 0.02
                feedback_parts.append(
                    f"Wrong assignment: {action.assigned_developer} "
                    f"(correct: {correct_dev}). "
                    f"Primary expert may be OOO!"
                )
        elif action.assigned_team:
            if (action.assigned_team.lower() in
                    correct_team.lower()):
                assign_score = 0.5
                feedback_parts.append(
                    f"Right team but should specify developer"
                )
            else:
                assign_score = 0.02
                feedback_parts.append(
                    f"Wrong team (expected {correct_team})"
                )
        else:
            assign_score = 0.02
            feedback_parts.append(
                f"No assignment given"
            )

    elif correct_team:
        if action.assigned_team:
            team_sim = text_similarity(
                action.assigned_team,
                correct_team
            )
            if team_sim >= 0.6:
                assign_score = 0.95
                feedback_parts.append(
                    f"Correct team assignment!"
                )
            else:
                assign_score = 0.02
                feedback_parts.append(
                    f"Wrong team (expected '{correct_team}')"
                )
        else:
            assign_score = 0.02
            feedback_parts.append(
                f"No team assigned"
            )
    else:
        assign_score = 0.95
        feedback_parts.append("No assignment check needed")

    breakdown["assignment"] = round(assign_score * 0.15, 2)

    # CHECK 7: Fixed Code (worth 0.05)
    if action.fixed_code and "fixed_code" in correct_answer:
        fix_score = check_fixed_code(
            action.fixed_code,
            correct_answer["fixed_code"]
        )
        breakdown["fixed_code"] = round(fix_score * 0.05, 2)

        if fix_score >= 0.9:
            feedback_parts.append("Fix is correct!")
        elif fix_score >= 0.4:
            feedback_parts.append("Fix is partially correct")
        else:
            feedback_parts.append("Fix is incorrect")
    else:
        breakdown["fixed_code"] = 0.01
        feedback_parts.append("No fix provided")

    # CHECK 8: Test Cases (bonus worth 0.10)
    if test_cases and action.fixed_code:
        test_score = run_tests_on_fix(
            action.fixed_code,
            test_cases
        )
        breakdown["tests_passed"] = round(test_score * 0.10, 2)
        passed_count = int(test_score * len(test_cases))
        feedback_parts.append(
            f"Tests: {passed_count}/{len(test_cases)} passed"
        )

    # CALCULATE TOTAL — clamp strictly between 0.01 and 0.99
    total_score = clamp(sum(breakdown.values()))
    feedback = " | ".join(feedback_parts)
    feedback += f" | Total: {total_score}/1.0"

    return Reward(
        score=total_score,
        max_score=0.99,
        feedback=feedback,
        breakdown=breakdown,
        is_correct=total_score >= 0.5
    )


# ================================================================
# MAIN GRADE FUNCTION
# ================================================================
def grade(action: Action, bug: dict) -> Reward:

    difficulty = bug["difficulty"]

    if difficulty == "easy":
        return grade_easy(action, bug)

    elif difficulty == "medium":
        return grade_medium(action, bug)

    elif difficulty == "hard":
        return grade_hard(action, bug)

    else:
        return Reward(
            score=0.01,
            max_score=0.99,
            feedback=f"Unknown difficulty: {difficulty}",
            breakdown={},
            is_correct=False
        )