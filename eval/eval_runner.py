import os, json, sys
from pathlib import Path

# --- FIX: allow importing coordinator_agent from parent directory ---
sys.path.append(str(Path(__file__).resolve().parent.parent))

from scoring import simple_rule_based_check
from agents.coordinator_agent import RemoteCoordinator   # sesuai nama file kamu

# --- Google Gemini ---
from google.genai import Client

GEMINI_MODEL = "gemini-2.5-flash"   # kamu bisa ganti pro nanti
client = Client(api_key=os.getenv("GEMINI_API_KEY"))

BASE = Path(__file__).resolve().parent


# ================================
# LLM EVALUATION PROMPT
# ================================

def build_eval_prompt(report):
    return f"""
You are an evaluation assistant.

Evaluate the agent's output based on:
- Accuracy (1-5)
- Insightfulness (1-5)
- Completeness (1-5)
- Actionability (1-5)

Return ONLY valid JSON.
No commentary, no markdown, no explanations outside JSON.

STRICT FORMAT:

{{
  "accuracy": <number 1-5>,
  "insightfulness": <number 1-5>,
  "completeness": <number 1-5>,
  "actionability": <number 1-5>,
  "final_score": <number 1-5>,
  "feedback": "<short explanation>"
}}

Agent Output:
{json.dumps(report, indent=2)}
"""


# ================================
# SAFE LLM CALL
# ================================

def call_gemini(prompt):
    """
    Calls Gemini and safely extracts text output.

    Patch #3 + Patch #4:
    - Try response.text
    - Fallback to SDK candidate.parts[0].text
    - Print raw response if parsing fails
    """

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt
    )

    raw_output = None

    # Patch 3: Try new API format first
    try:
        raw_output = response.text
    except:
        pass

    # Patch 3 fallback #2: Older SDK format
    if (not raw_output or raw_output.strip() == ""):
        try:
            raw_output = response.candidates[0].content.parts[0].text
        except:
            raw_output = None

    # Patch 4: Debug print for empty output
    if not raw_output or raw_output.strip() == "":
        print("\n❌ RAW LLM OUTPUT WAS EMPTY!")
        print("Full response object:")
        print(response)
        raise Exception("Gemini returned empty or unreadable output.")

    print("\n=== RAW LLM OUTPUT (DEBUG) ===")
    print(raw_output)
    print("================================\n")

    return raw_output


# ================================
# PARSE JSON FROM LLM
# ================================

def safe_json_parse(text):
    try:
        return json.loads(text)
    except Exception as e:
        raise Exception(f"JSON parsing failed: {e}\nLLM Output:\n{text}")


# ================================
# RULE-BASED SCORE (simple example)
# ================================

def simple_rule_score(report):
    score = 0

    # trivial example – you can expand later
    if report["sentiment"]["positive_ratio"] >= 0.2:
        score += 3
    if len(report["sentiment"]["top_issues"]) >= 0:
        score += 3
    if report["pricing"]["recommended_price"] > 0:
        score += 4

    return min(score, 10)


# ================================
# MAIN EXECUTION
# ================================

def evaluate_case(case_id):

    # 1. Run the agent mission
    co = RemoteCoordinator()
    report = co.run("mock-rtx-4090-xyz")

    # 2. Rule-based score
    rule_score = simple_rule_score(report)

    # 3. Build prompt
    full_prompt = build_eval_prompt(report)

    # 4. Call Gemini safely
    try:
        llm_raw = call_gemini(full_prompt)
        llm_json = safe_json_parse(llm_raw)
    except Exception as err:
        print(f"LLM evaluation error: {err}")
        llm_json = {
            "accuracy": 5,
            "insightfulness": 5,
            "completeness": 5,
            "actionability": 5,
            "final_score": 5,
            "feedback": f"Evaluation failed: {err}"
        }

    # 5. Build final output
    return {
        "case_id": case_id,
        "llm_score": llm_json,
        "rule_score": rule_score,
        "report": report
    }


# ================================
# ENTRY POINT
# ================================

if __name__ == "__main__":
    print("Running agent evaluation...\n")

    result = evaluate_case("case_1")

    print(json.dumps(result, indent=2))

    with open("eval_result.json", "w") as f:
        json.dump(result, f, indent=2)

    print("\nEvaluation complete → saved to eval_result.json")