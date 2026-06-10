

import json
import re
import time
import logging
from groq import Groq
from config import (
    GROQ_API_KEY, GROQ_MODEL, GROQ_MODEL_FAST,
    DEFAULT_QUESTION_COUNT, MAX_QUESTION_COUNT, MIN_QUESTION_COUNT
)

logger = logging.getLogger(__name__)

client = Groq(api_key=GROQ_API_KEY)


SYSTEM_PROMPTS = {
    "hindi": (
        "Aap ek expert teacher hain jo competitive exams (IBPS, SSC, UPSC) ke liye MCQ questions banate hain.\n"
        "\n"
        "IMPORTANT RULES:\n"
        "- Agar material mein koi Directions paragraph hai jiske basis par kai questions hain\n"
        "  (jaise seating arrangement, passage, family relation, data table), to us puri\n"
        "  direction ko EVERY related question ke 'directions' field mein ZAROOR include karein.\n"
        "- Bina directions ke questions incomplete hote hain - kabhi mat chhodein.\n"
        "- Standalone questions ke liye 'directions' empty string rakhein.\n"
        "- Sabhi questions aur options Hindi mein honein chahiye."
    ),
    "english": (
        "You are an expert educator creating MCQ questions for competitive exam preparation "
        "(IBPS, SSC, UPSC, CAT, etc.).\n"
        "\n"
        "CRITICAL RULES:\n"
        "- Many exam questions are part of a SET sharing a common Directions paragraph "
        "(seating arrangement, passage, data table, family tree, number series, etc.).\n"
        "- You MUST copy the FULL shared directions into the 'directions' field of EACH "
        "question in that set. A question without its directions is INCOMPLETE and UNSOLVABLE.\n"
        "- For standalone questions with no shared setup, set 'directions' to empty string.\n"
        "- All questions and options must be in English."
    ),
    "hinglish": (
        "Aap ek expert educator hain jo competitive exam (IBPS, SSC, UPSC) ke liye MCQ questions banate hain.\n"
        "\n"
        "IMPORTANT RULES:\n"
        "- Agar kai questions ek hi common setup/directions share karte hain (jaise seating "
        "arrangement, passage, family tree, data table), to us puri directions ko har related "
        "question ke 'directions' field mein ZAROOR likhein.\n"
        "- Bina direction ke questions incomplete hote hain.\n"
        "- Questions Hinglish mein honein chahiye."
    ),
}

USER_PROMPT_TEMPLATES = {
    "hindi": """\
Neeche di gayi study material ke aadhar par {count} MCQ questions banayein.
Sabhi questions aur options HINDI mein honein chahiye.

---
{text}
---

RULES:
1. Har question mein 4 options (A, B, C, D) aur sirf ek sahi answer hona chahiye.
2. Agar question kisi shared Directions/paragraph par based hai to us PURI direction ko
   'directions' field mein likhein. Standalone questions ke liye 'directions' empty rakhein.
3. Easy, medium aur hard questions ka mix rakhna.

Sirf JSON format mein jawab dein (koi aur text nahi):
{{
  "topic": "Mukhya vishay ka naam",
  "language": "hindi",
  "questions": [
    {{
      "id": 1,
      "directions": "Is question group ki puri shared directions yahan (ya empty string)",
      "question": "Question yahan?",
      "options": {{
        "A": "Option A",
        "B": "Option B",
        "C": "Option C",
        "D": "Option D"
      }},
      "correct_answer": "A",
      "explanation": "Sahi answer ki explanation."
    }}
  ]
}}""",

    "english": """\
Based on the following study material, generate {count} MCQ questions.
All questions and options must be in ENGLISH.

---
{text}
---

RULES:
1. Each question must have 4 options (A, B, C, D) and exactly one correct answer.
2. CRITICAL - Direction-based questions: If multiple questions share a common setup
   (passage, seating arrangement, data table, family tree, number series, etc.),
   copy the FULL shared directions into the "directions" field of EACH related question.
   Without this the question cannot be solved. For standalone questions set "directions" to "".
3. Mix difficulty: easy, medium, hard.
4. Base all questions strictly on the provided material.

Respond in JSON ONLY (no other text):
{{
  "topic": "Main topic name",
  "language": "english",
  "questions": [
    {{
      "id": 1,
      "directions": "Full shared directions/passage for this question group (empty string if standalone)",
      "question": "Question text here?",
      "options": {{
        "A": "Option A",
        "B": "Option B",
        "C": "Option C",
        "D": "Option D"
      }},
      "correct_answer": "A",
      "explanation": "Brief explanation of why this answer is correct."
    }}
  ]
}}""",

    "hinglish": """\
Neeche di gayi study material ke basis par {count} MCQ questions banao.
Questions HINGLISH mein honein chahiye.

---
{text}
---

RULES:
1. Har question mein 4 options (A, B, C, D), sirf ek sahi answer.
2. IMPORTANT - Agar kai questions ek hi common setup/directions share karte hain
   (jaise seating arrangement, passage, family tree, data table), to us puri directions ko
   har related question ke "directions" field mein ZAROOR likhein.
   Standalone questions ke liye "directions" ko "" rakhein.
3. Easy, medium aur hard questions ka mix rakhna.

Sirf JSON format mein answer do:
{{
  "topic": "Main topic ka naam",
  "language": "hinglish",
  "questions": [
    {{
      "id": 1,
      "directions": "Shared directions yahan (standalone ke liye empty)",
      "question": "Question yahan?",
      "options": {{
        "A": "Option A",
        "B": "Option B",
        "C": "Option C",
        "D": "Option D"
      }},
      "correct_answer": "A",
      "explanation": "Sahi answer ki explanation."
    }}
  ]
}}""",
}


def generate_mock_test(text, language="english", count=DEFAULT_QUESTION_COUNT):
    """Generate Mock Test."""
    language = language.lower().strip()
    if language not in SYSTEM_PROMPTS:
        language = "english"

    count = max(MIN_QUESTION_COUNT, min(MAX_QUESTION_COUNT, int(count)))

    if not text or len(text.strip()) < 100:
        return {
            "success": False,
            "error": "Extracted text is too short. Please upload a more detailed PDF.",
            "questions": [],
        }

    system_prompt = SYSTEM_PROMPTS[language]
    user_prompt = USER_PROMPT_TEMPLATES[language].format(text=text, count=count)


    max_tokens = min(8000, max(count * 300 + 500, 3000))

    raw_response = _call_groq(system_prompt, user_prompt, max_tokens=max_tokens)

    if not raw_response:
        return {
            "success": False,
            "error": "AI failed to generate questions. Please try again.",
            "questions": [],
        }

    return _parse_response(raw_response, language)


def _call_groq(system_prompt, user_prompt, max_tokens=4000):
    """Call Groq API with retry logic."""
    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_prompt},
                ],
                temperature=0.4,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.warning("Groq attempt %d failed: %s", attempt + 1, e)
            if attempt < 2:
                time.sleep(2 * (attempt + 1))
    return None


def _parse_response(raw, language):
    """Extract and validate JSON from Groq response."""
    # Strip markdown code fences if present
    raw = re.sub(r'^```(?:json)?\s*', '', raw.strip())
    raw = re.sub(r'\s*```$', '', raw.strip())

    #first 500 characters helps debug.
    logger.info("Groq raw response (first 500): %s", raw[:500])

    data = None

   
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        pass

    
    if data is None:
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group())
            except json.JSONDecodeError:
                pass

   
    if data is None:
        try:
        
            last_valid = raw.rfind('"correct_answer"')
            if last_valid > 0:
                
                end = raw.find('}', last_valid)
                if end > 0:
                    truncated = raw[:end+1] + ']}}'
                   
                    try:
                        data = json.loads(truncated)
                    except json.JSONDecodeError:
                        pass
        except Exception:
            pass

    if data is None:
        logger.error("All JSON parse attempts failed. Raw (first 1000): %s", raw[:1000])
        return {
            "success": False,
            "error": "AI returned malformed JSON. Please try again.",
            "questions": [],
        }

    questions = data.get("questions", [])
    valid_questions = []

    for i, q in enumerate(questions, 1):
        if not all(k in q for k in ("question", "options", "correct_answer")):
            continue
        options = q["options"]
        if not all(k in options for k in ("A", "B", "C", "D")):
            continue
        if q["correct_answer"] not in ("A", "B", "C", "D"):
            continue

        valid_questions.append({
            "id":             i,
            "directions":     q.get("directions", "").strip(),
            "question":       q["question"].strip(),
            "options":        {k: v.strip() for k, v in options.items()},
            "correct_answer": q["correct_answer"].upper(),
            "explanation":    q.get("explanation", "").strip(),
        })

    if not valid_questions:
        return {
            "success": False,
            "error": "AI generated questions in unexpected format. Please retry.",
            "questions": [],
        }

    return {
        "success":   True,
        "topic":     data.get("topic", "Study Material"),
        "language":  language,
        "questions": valid_questions,
        "total":     len(valid_questions),
        "error":     None,
    }
