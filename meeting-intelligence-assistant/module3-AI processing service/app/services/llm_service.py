# This is extremely important.
#
# It should be your single abstraction around the LLM provider.
#
# For example:
#
# class LLMService:
#     async def generate(...)
#     async def generate_structured(...)
# Then the rest of your code doesn't care whether you're using:
#
# Provider A
# Provider B
# Local model
# This makes switching models much easier.