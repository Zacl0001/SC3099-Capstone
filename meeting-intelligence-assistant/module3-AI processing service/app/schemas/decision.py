# Example:
#
# class Decision(BaseModel):
#     decision: str
#     evidence: str
#     timestamp: str | None
# This gives you:
#
# LLM
#  ↓
# JSON
#  ↓
# Pydantic validation
#  ↓
# Trusted application data
# rather than blindly trusting the LLM.