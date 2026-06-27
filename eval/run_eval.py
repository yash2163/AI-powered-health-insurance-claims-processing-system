import os
import sys
import json
from datetime import datetime
from typing import List, Dict, Any

# Ensure project root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config import POLICY_FILE_PATH, TEST_CASES_PATH
from app.services.policy_loader import load_policy
from app.services.test_case_loader import load_test_cases, test_case_to_claim, evaluate_result
from app.orchestrator.pipeline import ClaimsPipeline

def main():
    print("="*60)
    print("🏥 Plum Health Claims Processor — Evaluation Runner")
    print("="*60)
    
    # 1. Load config and policy
    if not os.path.exists(POLICY_FILE_PATH):
        print(f"ERROR: Policy file not found at {POLICY_FILE_PATH}")
        sys.exit(1)
        
    if not os.path.exists(TEST_CASES_PATH):
        print(f"ERROR: Test cases file not found at {TEST_CASES_PATH}")
        sys.exit(1)
        
    policy = load_policy(POLICY_FILE_PATH)
    test_cases = load_test_cases(TEST_CASES_PATH)
    
    print(f"Loaded policy: {policy.policy_name}")
    print(f"Loaded {len(test_cases)} test cases from {TEST_CASES_PATH}")
    print("-" * 60)
    
    # 2. Run pipeline for each test case
    pipeline = ClaimsPipeline(policy)
    results = []
    passed_count = 0
    
    for tc in test_cases:
        case_id = tc["case_id"]
        case_name = tc["case_name"]
        print(f"Running {case_id}: {case_name}...", end="", flush=True)
        
        claim = test_case_to_claim(tc)
        result = pipeline.process_claim(claim)
        eval_res = evaluate_result(tc, result)
        
        if eval_res["passed"]:
            print(" ✅ PASSED")
            passed_count += 1
        else:
            print(" ❌ FAILED")
            
        results.append({
            "tc": tc,
            "claim": claim,
            "result": result,
            "eval": eval_res
        })
        
    print("-" * 60)
    print(f"Result: {passed_count}/{len(test_cases)} passed successfully.")
    print("=" * 60)
    
    # 3. Generate Markdown Report
    os.makedirs(os.path.dirname(os.path.abspath(__file__)), exist_ok=True)
    report_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eval_report.md")
    
    with open(report_path, "w") as f:
        f.write(f"# Evaluation Report: Health Claims Processor\n\n")
        f.write(f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"## Summary\n\n")
        f.write(f"Total Test Cases: **{len(test_cases)}**  \n")
        f.write(f"Passed: **{passed_count}**  \n")
        f.write(f"Failed: **{len(test_cases) - passed_count}**  \n\n")
        
        # Summary Table
        f.write("### Test Results Grid\n\n")
        f.write("| TC ID | Name | Expected Decision | Expected Amount | Actual Decision | Actual Amount | Status |\n")
        f.write("|---|---|---|---|---|---|---|\n")
        for r in results:
            eval_info = r["eval"]
            status_emoji = "✅ PASSED" if eval_info["passed"] else "❌ FAILED"
            exp_amt = f"₹{eval_info['expected_amount']:,.2f}" if eval_info["expected_amount"] is not None else "—"
            act_amt = f"₹{eval_info['actual_amount']:,.2f}" if eval_info["actual_amount"] is not None else "—"
            f.write(f"| {r['tc']['case_id']} | {r['tc']['case_name']} | {eval_info['expected_decision']} | {exp_amt} | {eval_info['actual_decision']} | {act_amt} | {status_emoji} |\n")
            
        f.write("\n---\n\n")
        f.write("## Detailed Test Traces\n\n")
        
        for r in results:
            tc = r["tc"]
            eval_info = r["eval"]
            claim = r["claim"]
            result = r["result"]
            
            f.write(f"### {tc['case_id']}: {tc['case_name']}\n\n")
            f.write(f"**Description:** {tc['description']}  \n")
            f.write(f"**Status:** {'✅ PASSED' if eval_info['passed'] else '❌ FAILED'}  \n")
            f.write(f"**Notes:** {eval_info['notes']}  \n\n")
            
            f.write("#### Submission Details\n")
            f.write(f"- **Member ID:** `{claim.member_id}`\n")
            f.write(f"- **Claim Category:** `{claim.claim_category.value}`\n")
            f.write(f"- **Treatment Date:** `{claim.treatment_date.isoformat()}`\n")
            f.write(f"- **Claimed Amount:** `₹{claim.claimed_amount:,.2f}`\n\n")
            
            f.write("#### Execution Trace Logs\n\n")
            f.write("```json\n")
            
            # Serialize trace list from result
            if isinstance(result, dict):
                # Error dictionary trace
                trace_steps = result.get("trace", [])
            else:
                # ClaimDecision trace steps
                trace_steps = [step.model_dump() for step in result.trace.steps]
                
            f.write(json.dumps(trace_steps, indent=2, default=str))
                
            f.write("\n```\n\n")
            f.write("---\n\n")
            
    print(f"Report exported to: {report_path}")
    print("=" * 60)

if __name__ == "__main__":
    main()
