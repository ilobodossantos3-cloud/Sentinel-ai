import json
from typing import Literal

from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError

from app.core.config import settings


client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=settings.OPENROUTER_API_KEY,
)


SYSTEM_PROMPT = """
You are SentinelAI, a cybersecurity incident analysis engine.

Analyze Suricata security alerts.

IMPORTANT:
- Do not claim that a system was compromised unless the evidence proves it.
- Clearly distinguish observed evidence from hypotheses.
- A Suricata alert alone does not prove successful exploitation.
- Consider false positives.
- Do not invent information.

Return ONLY valid JSON.

Use exactly this structure:

{
  "threat_level": "LOW",
  "risk_score": 0,
  "classification": "",
  "confidence": 0.0,
  "analysis": "",
  "indicators": [],
  "recommended_actions": []
}

threat_level must be:
LOW, MEDIUM, HIGH, or CRITICAL.

risk_score must be an integer from 0 to 100.

confidence must be a number from 0 to 1.
"""


class AnalysisResult(BaseModel):
    """Validated output returned by the AI model."""

    threat_level: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    risk_score: int = Field(ge=0, le=100)
    classification: str
    confidence: float = Field(ge=0, le=1)
    analysis: str
    indicators: list = Field(default_factory=list)
    recommended_actions: list = Field(default_factory=list)


def analyze_incident(incident: dict) -> dict:

    prompt = f"""
Analyze this Suricata incident:

{json.dumps(incident, indent=2)}
"""

    response = client.chat.completions.create(
        model=settings.OPENROUTER_MODEL,
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        temperature=0.1,
    )

    content = response.choices[0].message.content

    # Remove markdown fences if the model returns them
    content = content.strip()

    if content.startswith("```json"):
        content = content[7:]

    elif content.startswith("```"):
        content = content[3:]

    if content.endswith("```"):
        content = content[:-3]

    content = content.strip()

    try:
        return AnalysisResult.model_validate_json(content).model_dump()
    except ValidationError as e:
        raise ValueError(
            f"AI returned an invalid analysis payload: {e}"
        ) from e