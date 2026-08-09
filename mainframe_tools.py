"""
Step 3: Individual Python tools for the Mainframe AI Assistant.
Each function does ONE job, reads from synthetic_jobs.json,
and is testable completely on its own -- no LLM involved yet.
"""

import json
import os

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "synthetic_jobs.json")


def _load_data():
    with open(DATA_PATH, "r") as f:
        return json.load(f)


def get_job_status(job_id):
    """
    Tool 1: Look up a job's current status by job ID.
    Handles the case where the job ID doesn't exist at all.
    """
    data = _load_data()
    job_id = job_id.strip().upper()

    for job in data["jobs"]:
        if job["job_id"] == job_id:
            return {
                "job_id": job["job_id"],
                "status": job["status"],
                "retcode": job["retcode"],
                "step": job["step"],
                "program": job["program"]
            }

    return {"error": f"No job found with ID '{job_id}'. Check the job ID and try again."}


def check_abend(retcode):
    """
    Tool 2: Classify an abend/return code using the known abend dictionary.
    Handles unknown/unrecognized codes without guessing.
    """
    data = _load_data()
    retcode = retcode.strip().upper()

    if retcode == "0000":
        return {"classification": "Job completed successfully -- not an abend."}

    known = data["abend_codes"]
    if retcode in known:
        return {"retcode": retcode, "classification": known[retcode]}

    return {"error": f"Unrecognized abend code '{retcode}'. Not in known classification list -- manual review needed."}


def check_jcl(job_id):
    """
    Tool 3: Pull the raw log snippet for a job -- simulates checking JCL/job log output.
    """
    data = _load_data()
    job_id = job_id.strip().upper()

    for job in data["jobs"]:
        if job["job_id"] == job_id:
            return {"job_id": job_id, "log_snippet": job["log_snippet"]}

    return {"error": f"No log data found for job ID '{job_id}'."}


def check_rerun_eligibility(retcode):
    """
    Tool 4: Decide if a job is safe to rerun based on its abend code.
    """
    retcode = retcode.strip().upper()

    rerun_safe = {"S222"}          # operator-cancelled -- usually safe to just rerun
    rerun_unsafe = {"S806", "S0C7", "S0C4", "S013"}  # needs investigation first

    if retcode in rerun_safe:
        return {"safe_to_rerun": True, "reason": "This abend type is typically not caused by a data or program defect."}
    if retcode in rerun_unsafe:
        return {"safe_to_rerun": False, "reason": "This abend usually indicates a program or data problem -- investigate before rerunning."}
    return {"safe_to_rerun": None, "reason": "Unknown abend code -- manual review recommended before any rerun decision."}


def rerun_job(job_id, human_approved):
    """
    Tool 5: MOCK rerun action -- simulates resubmitting a job.
    This is the human-in-the-loop gate: this function will REFUSE to
    'run' unless human_approved is explicitly True. The agent itself
    can never set this to True on its own -- only a real human response
    in the conversation loop can.
    """
    if not human_approved:
        return {
            "executed": False,
            "message": f"Rerun of job '{job_id}' was NOT executed -- waiting for human approval."
        }

    # This is a MOCK action -- no real system is touched. In a real
    # production version, this is where an actual resubmit command
    # (e.g. via Zowe CLI) would go, still gated behind this same check.
    return {
        "executed": True,
        "message": f"[MOCK] Job '{job_id}' has been resubmitted for execution."
    }


if __name__ == "__main__":
    # Quick manual tests -- proving each tool works BEFORE any LLM is involved
    print("=== get_job_status tests ===")
    print(get_job_status("PAYJOB01"))
    print(get_job_status("ZZZZZZ"))  # doesn't exist -- should return error, not crash

    print("\n=== check_abend tests ===")
    print(check_abend("S0C7"))
    print(check_abend("SXXX"))  # unknown code -- should return error, not guess

    print("\n=== check_jcl tests ===")
    print(check_jcl("DEPTJOB01"))

    print("\n=== check_rerun_eligibility tests ===")
    print(check_rerun_eligibility("S222"))
    print(check_rerun_eligibility("S0C7"))
