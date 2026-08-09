"""
Step 9: Test the agent against multiple different failure scenarios in one run.
This proves the agent behaves consistently across different situations,
not just the one or two cases we tested manually.

Note: the rerun_job test cases here will pause for human approval --
that's expected and correct, not a bug.
"""

import sys
import os

# Let this file import agent.py from the parent folder
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from agent import ask_agent

TEST_CASES = [
    {
        "label": "Normal abend lookup (S0C7)",
        "question": "Why did job PAYJOB01 fail?"
    },
    {
        "label": "Different abend type (S806 - missing program)",
        "question": "What's wrong with job PAYJOB02?"
    },
    {
        "label": "Dataset/DD issue (S013)",
        "question": "Why did job DEPTJOB01 fail?"
    },
    {
        "label": "Successful job (should NOT diagnose a failure)",
        "question": "What's the status of job NUMJOB02?"
    },
    {
        "label": "Nonexistent job ID (bad input)",
        "question": "What's the status of job FAKEJOB123?"
    },
    {
        "label": "Unknown/unrecognized abend code",
        "question": "Why did job UNKNOWNJOB99 fail?"
    },
    {
        "label": "Multi-step: diagnosis + rerun eligibility",
        "question": "Why did job DEPTJOB02 fail, and is it safe to rerun?"
    },
]

if __name__ == "__main__":
    print(f"Running {len(TEST_CASES)} test scenarios...\n")
    print("=" * 70)

    for i, case in enumerate(TEST_CASES, 1):
        print(f"\nTEST {i}: {case['label']}")
        print("-" * 70)
        ask_agent(case["question"])
        print("=" * 70)

    print("\nAll test scenarios completed. Review the output above for any")
    print("unexpected behavior (wrong diagnosis, crashes, or hallucinated codes).")
