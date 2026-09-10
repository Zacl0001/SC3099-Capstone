This becomes your API contract.

Document endpoints like:

POST /api/auth/register

POST /api/auth/login

GET /api/meetings

POST /api/meetings

GET /api/meetings/{id}

POST /api/meetings/{id}/transcript

POST /api/meetings/{id}/process

GET /api/meetings/{id}/summary

GET /api/meetings/{id}/action-items

GET /api/meetings/{id}/decisions

POST /api/meetings/{id}/chat
For each:

Endpoint
Method
Authentication
Request body
Response
Errors