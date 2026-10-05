import os
from dotenv import load_dotenv

load_dotenv()

# Rule 2.6: Canonical constant
GITHUB_LOOKUP_TIMEOUT_SECONDS = 10

# Allowlist of GitHub Enterprise hosts
# Comma-separated list of hostnames, e.g., github.enterprise.myorg.com
PERMITTED_GHE_HOSTS_STR = os.environ.get("PERMITTED_GHE_HOSTS", "")
PERMITTED_GHE_HOSTS = [
    host.strip() for host in PERMITTED_GHE_HOSTS_STR.split(",") if host.strip()
]

# Platform-held read-only GitHub token for unauthenticated metadata checks
GITHUB_METADATA_TOKEN = os.environ.get("GITHUB_METADATA_TOKEN")
