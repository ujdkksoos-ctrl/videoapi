#!/usr/bin/env bash
# Install Deno locally in the Render environment
curl -fsSL https://deno.land/install.sh | sh

# Export Deno to the PATH
export PATH="/opt/render/.deno/bin:$PATH"

# Install Python requirements
pip install -r requirements.txt
