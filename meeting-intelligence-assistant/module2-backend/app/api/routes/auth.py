# api/routes/auth.py
# Endpoints:
#
# POST /auth/register
# POST /auth/login
# GET /auth/me
# Responsibilities:
#
# Validate input
# Call auth service
# Return JWT/user information
# Don't put password hashing/business logic directly here.