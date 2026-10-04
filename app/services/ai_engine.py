import json
import re

import requests

from app.core.config import settings


class AIEngineError(Exception):
    """Raised when we can't get a usable response from the AI backend."""
    pass

#====================================================================================================================================
#Groq Model
#====================================================================================================================================
def ask_groq(prompt: str, temperature: float = 0.7) -> str:
    """
    Send a prompt to Groq's cloud API and get back the AI's text response.
    Same job as ask_ollama, just talking to Groq's cloud servers instead of
    a local Ollama process — no model to keep running on your own machine.
    """
    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.groq_api_key}"},
            json={
                "model": settings.groq_model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
            },
            timeout=60,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

    except requests.exceptions.ConnectionError:
        raise AIEngineError("Could not connect to Groq. Check your internet connection.")
    except requests.exceptions.Timeout:
        raise AIEngineError("Groq took too long to respond. Try again.")
    except requests.exceptions.HTTPError:
        raise AIEngineError(
            f"Groq API error ({response.status_code}): {response.text}. "
            "Check that GROQ_API_KEY and GROQ_MODEL in your .env are correct."
        )
#====================================================================================================================================
# Analyse code
#====================================================================================================================================
def analyze_code(code_content: str, language: str) -> dict:
    """
    Ask the AI to analyze a piece of code and return a dict with:
        - complexity: "Low" | "Medium" | "High"
        - quality_score: a number from 0-10
        - explanation: a short plain-English summary of what the code does

    We ask the AI to reply in JSON so we can save these as separate, structured
    fields in the AnalysisReport table (instead of one big blob of text).
    """
    prompt = f"""You are a code analysis assistant. Analyze the following {language} code.

Respond with ONLY valid JSON, no other text, no markdown formatting, in exactly this format:
{{"complexity": "Low", "quality_score": 8.5, "explanation": "a 2-3 sentence explanation of what this code does"}}

complexity must be one of: "Low", "Medium", "High"
quality_score must be a number between 0 and 10

Code to analyze:
{code_content}
"""

    raw_reply = ask_groq(prompt, temperature=0.0)
    return _parse_analysis_reply(raw_reply)


def _parse_analysis_reply(raw_reply: str) -> dict:
    """
    Small local models don't always follow "reply with ONLY JSON" perfectly —
    they sometimes wrap it in markdown code fences, or add a sentence before/after.
    This function tries to pull out just the JSON part and parse it safely.

    If parsing fails entirely, we don't crash — we fall back to storing the AI's
    raw reply as the explanation, so the user still gets *something* useful,
    rather than a failed request.
    """
    match = re.search(r"\{.*\}", raw_reply, re.DOTALL)

    if match:
        try:
            parsed = json.loads(match.group())
            return {
                "complexity": parsed.get("complexity", "Unknown"),
                "quality_score": parsed.get("quality_score"),
                "explanation": parsed.get("explanation", raw_reply),
            }
        except json.JSONDecodeError:
            pass  # fall through to the fallback below

    # Fallback: couldn't parse JSON at all — still save something useful
    return {
        "complexity": "Unknown",
        "quality_score": None,
        "explanation": raw_reply,
    }

#====================================================================================================================================
# Generate test cases
#====================================================================================================================================
def generate_test_cases(code_content: str, language: str) -> list[dict]:
    """
    Ask the AI to generate software test cases for a piece of code.
    Returns a list of dicts, each with: test_type, description, expected_result.

    Matches your synopsis's objective: "generate functional, positive, negative,
    boundary value, and edge-case test cases."
    """
    prompt = f"""You are a meticulous software testing assistant. Generate test cases for the following {language} code.

Before writing each test case, trace through the code carefully:
- Copy the EXACT text of print/output statements from the source code — do not paraphrase or reword them.
- If a print statement uses a variable (e.g. an f-string like f"Task {{r}} done"), figure out exactly what that
  variable actually holds at that point in the code — not what its name suggests. For example, if a variable is
  reassigned by something like list.pop(index), it now holds the POPPED VALUE, not the original index the user typed.
- If some input could cause an unhandled crash (e.g. IndexError from an out-of-range index, ValueError from
  converting bad input to int, FileNotFoundError from opening a missing file), that is a valid, useful test case —
  set expected_result to describe that crash/exception, not a made-up success message.
- Do not merge two different scenarios into one test case (e.g. "empty list" and "invalid index" are different
  situations with different actual outcomes — keep them separate).

Here is a worked example showing the level of precision expected:

Example code:
def divide(a, b):
    if b == 0:
        return "Error: division by zero"
    return a / b

Correct test cases for the example above:
[
  {{"test_type": "Positive", "description": "Divide 10 by 2", "expected_result": "5.0 (a float, since / always returns a float in Python)"}},
  {{"test_type": "Negative", "description": "Divide by zero, e.g. divide(10, 0)", "expected_result": "Error: division by zero"}},
  {{"test_type": "Boundary", "description": "Divide 0 by a non-zero number, e.g. divide(0, 5)", "expected_result": "0.0"}}
]

Notice: the division result is "5.0" not "5" (matching Python's actual float behavior), and the zero-division
case correctly uses the code's own handled error message rather than assuming a crash — because this code
already checks for b == 0 before dividing. Trace each function this precisely.

Now respond with ONLY a valid JSON array, no other text, no markdown formatting, in exactly this format:
[
  {{"test_type": "Positive", "description": "short description of the test", "expected_result": "what should happen"}},
  {{"test_type": "Negative", "description": "...", "expected_result": "..."}}
]

Include a mix of test types: Positive, Negative, Boundary, and Edge Case.
Generate between 4 and 8 test cases depending on how many make sense for this code.

Code to generate test cases for:
{code_content}
"""

    # Lower temperature than the default — we want precise, literal tracing here,
    # not creative variety, so we turn down the model's randomness.
    raw_reply = ask_groq(prompt, temperature=0.0)
    return _parse_test_case_reply(raw_reply)


def _parse_test_case_reply(raw_reply: str) -> list[dict]:
    """
    Same idea as _parse_analysis_reply, but for a JSON *array* instead of one object.
    If the model's reply can't be parsed at all, we return an empty list rather than
    crashing — the endpoint will just save zero test cases and the user can retry.
    """
    match = re.search(r"\[.*\]", raw_reply, re.DOTALL)

    if match:
        try:
            parsed = json.loads(match.group())
            # Only keep items that actually have the fields we need — skip anything malformed
            return [
                item for item in parsed
                if isinstance(item, dict) and "description" in item and "expected_result" in item
            ]
        except json.JSONDecodeError:
            pass

    return []
#====================================================================================================================================
# Analyze Security
#====================================================================================================================================
def analyze_security(code_content: str, language: str) -> dict:
    """
    Ask the AI to review a piece of code for security issues.
    Returns a dict with: issue_description, severity, recommendation, security_score.
    """
    prompt = f"""You are a security analysis assistant. Review the following {language} code for security issues.

Look for common issues such as: hardcoded credentials/secrets, missing password hashing, missing
authentication or authorization checks, SQL injection risk, missing input validation, insecure file
handling, and exposed sensitive data.

Respond with ONLY valid JSON, no other text, no markdown formatting, in exactly this format:
{{"issue_description": "a description of the security issues found, or state that none were found", "severity": "Medium", "recommendation": "specific steps to fix the issues found", "security_score": 6.0}}

severity must be one of: "Low", "Medium", "High"
security_score must be a number between 0 (very insecure) and 10 (very secure)

Code to analyze:
{code_content}
"""

    raw_reply = ask_groq(prompt, temperature=0.2)
    return _parse_security_reply(raw_reply)


def _parse_security_reply(raw_reply: str) -> dict:
    """
    Same safe-parsing idea as _parse_analysis_reply. If parsing fails entirely,
    we still need to save *something* — SecurityAnalysis's columns are all
    required (NOT NULL), so the fallback can't leave anything as None.
    """
    match = re.search(r"\{.*\}", raw_reply, re.DOTALL)

    if match:
        try:
            parsed = json.loads(match.group())
            return {
                "issue_description": parsed.get("issue_description", raw_reply),
                "severity": parsed.get("severity", "Unknown"),
                "recommendation": parsed.get("recommendation", "Re-run the analysis."),
                "security_score": parsed.get("security_score", 0.0),
            }
        except json.JSONDecodeError:
            pass

    return {
        "issue_description": f"Could not fully parse the AI's response. Raw output: {raw_reply}",
        "severity": "Unknown",
        "recommendation": "Re-run the analysis; the AI's response could not be parsed as JSON.",
        "security_score": 0.0,
    }
#====================================================================================================================================
# Single Project documentation
#====================================================================================================================================
def generate_documentation(code_content: str, language: str) -> str:
    """
    Ask the AI to generate documentation for a piece of code.

    Unlike analyze_code/generate_test_cases/analyze_security, this returns
    plain text directly — no JSON parsing needed, since documentation is just
    one block of readable text rather than several separate structured fields.
    """
    prompt = f"""You are a technical writer generating documentation for the following {language} code.

Write clear, concise documentation that includes:
- A short overview of what the code does
- For each function: its purpose, its parameters, and what it returns or prints
- Any important behavior a developer should know about (e.g. side effects, file I/O, error handling)

Write in plain text or simple markdown. Do not include the source code itself in your response —
just the documentation describing it.

Code to document:
{code_content}
"""

    return ask_groq(prompt, temperature=0.3)

#====================================================================================================================================
# Chat with Ai
#====================================================================================================================================
def chat_with_ai(history: list[dict], new_message: str) -> str:
    """
    Continue a conversation with the AI assistant about a project.

    Unlike the other four functions, this isn't a one-off "send a prompt, get an
    answer" call — `history` carries the earlier back-and-forth in this project's
    chat (each item like {"role": "user", "content": "..."} or
    {"role": "assistant", "content": "..."}), so the AI has context of what's
    already been discussed, instead of treating every message as the first one.
    """
    system_message = {
        "role": "system",
        "content": (
            "You are a helpful AI assistant inside a software testing tool. "
            "You help developers understand their code, generated test cases, "
            "security findings, and documentation. Keep answers clear and concise."
        ),
    }
    messages = [system_message] + history + [{"role": "user", "content": new_message}]

    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.groq_api_key}"},
            json={"model": settings.groq_model, "messages": messages, "temperature": 0.7},
            timeout=60,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except requests.exceptions.ConnectionError:
        raise AIEngineError("Could not connect to Groq. Check your internet connection.")
    except requests.exceptions.Timeout:
        raise AIEngineError("Groq took too long to respond. Try again.")
    except requests.exceptions.HTTPError:
        raise AIEngineError(f"Groq API error: {response.text}. Check GROQ_API_KEY and GROQ_MODEL in your .env.")


#====================================================================================================================================
# Overall project analysis
#====================================================================================================================================

def analyze_project_overview(file_analyses: list[dict], file_securities: list[dict]) -> dict:
    """
    Build a project-wide overview and security summary from EXISTING per-file
    results — not by re-reading raw code. Keeps this call small regardless of
    project size, since it's built from short summaries, not full source.
    """
    if not file_analyses and not file_securities:
        return {
            "overview": "No individual file analyses available yet. Run /analyze on your files first.",
            "security_summary": "No individual security analyses available yet. Run /analyze-security on your files first.",
        }

    analyses_text = "\n".join(f"- {a['file_name']}: {a['explanation_summary']}" for a in file_analyses) or "(none yet)"
    security_text = "\n".join(
        f"- {s['file_name']}: {s['issue_description']} (Severity: {s['severity']})" for s in file_securities
    ) or "(none yet)"

    prompt = f"""You are reviewing a multi-file software project as a whole, based on summaries of
each file's individual analysis — not the raw code itself.

Per-file explanations:
{analyses_text}

Per-file security findings:
{security_text}

Respond with ONLY valid JSON, no other text, no markdown formatting, in exactly this format:
{{"overview": "a cohesive paragraph describing what this project does as a whole, based on the file summaries above", "security_summary": "a cohesive paragraph summarizing the overall security posture across the project, based on the findings above"}}
"""

    raw_reply = ask_groq(prompt, temperature=0.2)
    return _parse_project_reply(raw_reply)


def _parse_project_reply(raw_reply: str) -> dict:
    match = re.search(r"\{.*\}", raw_reply, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group())
            return {
                "overview": parsed.get("overview", raw_reply),
                "security_summary": parsed.get("security_summary", "Could not generate a security summary."),
            }
        except json.JSONDecodeError:
            pass

    return {
        "overview": f"Could not fully parse the AI's response. Raw output: {raw_reply}",
        "security_summary": "Could not fully parse the AI's response.",
    }

#====================================================================================================================================
# Overall project documentation
#====================================================================================================================================
def generate_project_documentation(
    overview: str,
    security_summary: str,
    average_quality_score: float | None,
    average_security_score: float | None,
    average_complexity: str | None,
) -> str:
    """
    Ask the AI to write project-level documentation, based on the ALREADY-COMPUTED
    ProjectAnalysis fields — not raw code.
    """
    quality_line = f"{average_quality_score:.1f}/10" if average_quality_score is not None else "not yet available"
    security_line = f"{average_security_score:.1f}/10" if average_security_score is not None else "not yet available"
    complexity_line = average_complexity or "not yet available"

    prompt = f"""You are a technical writer creating project-level documentation for a software project,
based on the summary below (not raw code).

Project overview:
{overview}

Security summary:
{security_summary}

Average code quality score: {quality_line}
Average security score: {security_line}
Average complexity: {complexity_line}

Write clear, well-organized documentation covering: what the project does, its overall code
quality and complexity, and its overall security posture with any notable recommendations.
Plain text or simple markdown only.
"""

    return ask_groq(prompt, temperature=0.3)