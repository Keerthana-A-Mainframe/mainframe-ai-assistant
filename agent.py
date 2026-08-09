"""
Step 4: Connect a local LLM (Qwen 2.5 3B via Ollama) to our mainframe tools.

Same core pattern as before (ask -> decide -> execute -> explain),
just using Ollama's local model instead of Claude's API.
No API key, no internet needed after the model is downloaded, no cost.
"""

import ollama
import json
import sys
import os

# Let this file import mainframe_tools.py from the tools/ folder
sys.path.append(os.path.join(os.path.dirname(__file__), "tools"))
from mainframe_tools import get_job_status, check_abend, check_jcl, check_rerun_eligibility, rerun_job

MODEL_NAME = "qwen2.5:3b"

# ---- Layer 2 safety check (v2): cross-check against REAL data already fetched ----
# Instead of guessing codes from the user's wording (which broke on words like
# "SAFE" being mistaken for a code -- S+AFE matched our old pattern), we now
# track the actual retcode returned by get_job_status earlier in the SAME
# conversation, and treat that as ground truth.

def validate_tool_call(fn_name, fn_args, known_retcode):
    """
    Layer 2 check (v2): if we've already fetched a real retcode via
    get_job_status in this conversation, make sure check_abend /
    check_rerun_eligibility are using THAT actual code, not a substituted one.
    Returns (is_valid, corrected_args).
    """
    if fn_name not in ("check_abend", "check_rerun_eligibility"):
        return True, fn_args  # this check only applies to code-based tools

    if not known_retcode:
        return True, fn_args  # no real data fetched yet, nothing to cross-check

    called_code = fn_args.get("retcode", "").upper()

    if called_code == known_retcode.upper():
        return True, fn_args  # matches the real data we already fetched

    # Mismatch detected -- the model substituted a different code
    print(f"  [SAFETY CHECK] Model tried '{called_code}' but the real fetched "
          f"retcode is '{known_retcode}' -- correcting.")
    corrected_args = dict(fn_args)
    corrected_args["retcode"] = known_retcode
    return False, corrected_args

# ---- Tool definitions the model can see ----
# Ollama uses the same JSON-schema style as Claude's tool use.
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_job_status",
            "description": "Gets the current status of a mainframe batch job by job ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "job_id": {"type": "string", "description": "The mainframe job ID, e.g. PAYJOB01"}
                },
                "required": ["job_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_abend",
            "description": "Classifies an abend/return code into a plain explanation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "retcode": {"type": "string", "description": "The abend/return code, e.g. S0C7"}
                },
                "required": ["retcode"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_jcl",
            "description": "Gets the raw job log snippet for a given job ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "job_id": {"type": "string", "description": "The mainframe job ID"}
                },
                "required": ["job_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_rerun_eligibility",
            "description": "Checks if a job is safe to rerun based on its abend code. Call this AFTER get_job_status if the job failed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "retcode": {"type": "string", "description": "The abend/return code"}
                },
                "required": ["retcode"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "rerun_job",
            "description": (
                "Resubmits a failed job for execution. This is a real action, not just "
                "information -- only call this if the user has clearly asked you to rerun "
                "the job, AFTER you've already checked rerun eligibility."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "job_id": {"type": "string", "description": "The mainframe job ID to rerun"}
                },
                "required": ["job_id"]
            }
        }
    }
]

# Map tool names to the real Python functions that execute them
AVAILABLE_FUNCTIONS = {
    "get_job_status": lambda args: get_job_status(args["job_id"]),
    "check_abend": lambda args: check_abend(args["retcode"]),
    "check_jcl": lambda args: check_jcl(args["job_id"]),
    "check_rerun_eligibility": lambda args: check_rerun_eligibility(args["retcode"]),
    # rerun_job is deliberately NOT in this dict -- it's handled specially
    # below so we can force a real human approval step before it runs.
}


SYSTEM_PROMPT = (
    "You are a mainframe troubleshooting assistant. You have access to tools "
    "for checking job status, classifying abend codes, checking job logs, "
    "checking rerun eligibility, and rerunning a job. "
    "IMPORTANT: If you need information from a tool, you must actually CALL that "
    "tool -- never just say you are going to call it or describe what you plan to do. "
    "Only respond with plain text once you have all the information you need from "
    "the tools you've already called. "
    "CRITICAL: If the user explicitly asks you to rerun, resubmit, or restart a job, "
    "you MUST call the rerun_job tool -- do not just say it's safe to rerun in plain "
    "text. Calling rerun_job is how the actual rerun approval process starts."
)


def ask_agent(user_question, max_steps=5):
    """
    The multi-step loop: ask -> model decides -> Python executes -> result goes back -> repeat.
    max_steps prevents infinite loops if something goes wrong.
    """
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_question}
    ]
    print(f"\nUSER: {user_question}")

    known_retcode = None  # tracks the REAL retcode once get_job_status returns one

    for step in range(max_steps):
        response = ollama.chat(
            model=MODEL_NAME,
            messages=messages,
            tools=tools
        )

        msg = response["message"]
        messages.append(msg)

        # Does the model want to call a tool?
        if "tool_calls" in msg and msg["tool_calls"]:
            for call in msg["tool_calls"]:
                fn_name = call["function"]["name"]
                fn_args = call["function"]["arguments"]
                print(f"  [Step {step+1}] MODEL CALLS: {fn_name}({fn_args})")

                # Layer 2 safety check -- catch code substitution before running the tool,
                # using REAL data already fetched (not guesses from user wording)
                is_valid, fn_args = validate_tool_call(fn_name, fn_args, known_retcode)
                if not is_valid:
                    print(f"  [Step {step+1}] CORRECTED ARGS: {fn_args}")

                # ---- Human-in-the-loop gate ----
                # rerun_job is a real action, not just information. The model
                # can REQUEST it, but a real human must approve it here, live,
                # before anything happens. The model never controls this.
                if fn_name == "rerun_job":
                    job_id = fn_args.get("job_id")
                    answer = input(
                        f"\n  [APPROVAL NEEDED] Agent wants to rerun job '{job_id}'. "
                        f"Approve? (yes/no): "
                    ).strip().lower()
                    human_approved = answer in ("yes", "y")
                    result = rerun_job(job_id, human_approved)

                elif fn_name in AVAILABLE_FUNCTIONS:
                    result = AVAILABLE_FUNCTIONS[fn_name](fn_args)
                else:
                    result = {"error": f"Unknown tool requested: {fn_name}"}

                print(f"  [Step {step+1}] TOOL RESULT: {result}")

                # If this was a successful get_job_status call, remember its
                # real retcode as ground truth for the rest of the conversation
                if fn_name == "get_job_status" and "retcode" in result:
                    known_retcode = result["retcode"]

                # Feed the result back so the model can decide the next step
                messages.append({
                    "role": "tool",
                    "content": json.dumps(result)
                })

                # If we corrected the code, add an extra reminder so the model's
                # FINAL WRITTEN ANSWER also uses the right code, not the one it
                # originally (wrongly) tried.
                if not is_valid:
                    messages.append({
                        "role": "user",
                        "content": (
                            f"Note: the correct code being discussed is '{fn_args.get('retcode')}'. "
                            f"Use this exact code in your response, not any other code."
                        )
                    })
        else:
            # No more tool calls -- this is the final answer
            print(f"\nAGENT'S FINAL ANSWER:\n{msg['content']}")
            return msg["content"]

    print("\n[Stopped -- reached max steps without a final answer]")
    return None


if __name__ == "__main__":
    ask_agent("What's the status of job PAYJOB01?")
