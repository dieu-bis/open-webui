PORT="${PORT:-8080}"

# Load environment variables from .env file if it exists
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Export Atlassian integration environment variable for development
export ENABLE_ATLASSIAN_INTEGRATION=true
export ATLASSIAN_CLIENT_ID=EdCGzLBDqBLnBZ0XkeYGnkqTAhJJVqrS
export ATLASSIAN_CLIENT_SECRET=ATOABp_NAXQNVF4HJvJi70EASHnA_5nGN0L4z3txhaoOs3gwESfFRcoU_XYT8FbrXJ2qD2B638F0
export ATLASSIAN_REDIRECT_URI=http://localhost:5173/settings/connections
export ATLASSIAN_OAUTH_SCOPE="read:me read:jira-user read:jira-work read:confluence-content.all read:space:confluence offline_access"

# Enable CORS for development
export CORS_ALLOW_ORIGIN="http://localhost:5173;http://localhost:8080"

uvicorn open_webui.main:app --port $PORT --host 0.0.0.0 --forwarded-allow-ips '*' --reload