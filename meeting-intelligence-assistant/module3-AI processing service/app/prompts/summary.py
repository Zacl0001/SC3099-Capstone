# Contains your summary prompt templates.
#
# Don't write:
#
# prompt = "summarize this"
# and stop there.
#
# You want something more controlled:
#
# You are a meeting analysis assistant.
#
# Analyze the transcript below.
#
# Return:
# 1. Executive summary
# 2. Key discussion points
# 3. Important outcomes
#
# Do not invent information.
# Only use information explicitly stated in the transcript.
#
# TRANSCRIPT:
# ...
# Eventually have:
#
# SUMMARY_PROMPT_V1
# SUMMARY_PROMPT_V2
# so you can compare approaches.