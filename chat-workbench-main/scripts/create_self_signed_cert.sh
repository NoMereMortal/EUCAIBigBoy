#!/usr/bin/env bash
# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

# ========================================================================
# Self-Signed Certificate Creation Script
# ========================================================================
#
# DESCRIPTION:
#   Generates a self-signed SSL certificate and uploads it to AWS IAM
#   for use with Application Load Balancers (ALBs), particularly for
#   development or testing environments.
#
# USAGE:
#   ./scripts/create_self_signed_cert.sh <certificate-name>
#
# ARGUMENTS:
#   <certificate-name>    The name to assign to the server certificate in IAM.
#
# PREREQUISITES:
#   - OpenSSL must be installed.
#   - AWS CLI must be installed and configured with permissions to
#     iam:UploadServerCertificate.
#
# ENVIRONMENT VARIABLES:
#   REGION                The AWS region where the ALB is located. This is
#                         used to generate a wildcard domain for the cert
#                         (e.g., *.us-east-1.elb.amazonaws.com).
#
# ========================================================================

set -euo pipefail

# Usage: ./create_self_signed_cert.sh <certificate-name>
if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <certificate-name>"
  exit 1
fi

CERT_NAME="$1"

if [[ -z "${REGION:-}" ]]; then
  echo "Error: REGION must be set." >&2
  exit 1
fi

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
CERT_PATH="$SCRIPT_DIR/server.pem"
KEY_PATH="$SCRIPT_DIR/server.key"
DOMAIN="*.$REGION.elb.amazonaws.com"

# Generate cert/key if they don’t already exist
if [[ ! -f "$CERT_PATH" || ! -f "$KEY_PATH" ]]; then
  openssl req -x509 -newkey rsa:4096 -sha256 -days 365 \
    -nodes -keyout "$KEY_PATH" -out "$CERT_PATH" \
    -subj "/CN=$DOMAIN" -addext "subjectAltName=DNS:$DOMAIN" &>/dev/null
  echo "Generated self-signed certificate for $DOMAIN"
else
  echo "Using cached certificate and key"
fi

# Upload to AWS IAM
aws iam upload-server-certificate \
  --server-certificate-name "$CERT_NAME" \
  --certificate-body file://"$CERT_PATH" \
  --private-key file://"$KEY_PATH"

echo "Certificate '$CERT_NAME' uploaded to IAM."
