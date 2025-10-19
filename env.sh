#!/bin/bash
# Environment variables for agents projects
# Source this file before running any scripts: source env.sh

# OpenAI API Key (required for openai-agents-python)
# export OPENAI_API_KEY="your-openai-api-key-here"

# AWS Configuration
# Option 1: Use AWS Profile (recommended for SSO)
# NOTE: Profile names are case sensitive. Use the exact name from `aws configure sso list-profiles`.
# The DS-MCP scripts default to `3VDEV` if not set; align with that here by default.
export AWS_PROFILE="3VDEV"

# Option 2: Use static AWS credentials (uncomment if not using profile)
# export AWS_ACCESS_KEY_ID="your-access-key-id"
# export AWS_SECRET_ACCESS_KEY="your-secret-access-key"
# export AWS_SESSION_TOKEN="your-session-token"  # If using temporary credentials

# AWS Region
export AWS_DEFAULT_REGION="us-east-1"

# Additional environment variables as needed
# export REDSHIFT_ENDPOINT="your-redshift-endpoint"
# export DATABASE_NAME="your-database-name"

# Do not write to stdout in MCP stdio contexts; log to stderr.
echo "Environment variables loaded from env.sh" >&2
