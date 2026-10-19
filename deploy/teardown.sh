#!/usr/bin/env bash
# Delete everything deploy.sh created: instance, security group, key pair,
# IAM role + instance profile. Safe to re-run; skips what is already gone.
#
# Usage:
#   AWS_PROFILE=lab ./deploy/teardown.sh
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STATE_DIR="$ROOT/deploy/.state"
STATE="$STATE_DIR/state.env"

# shellcheck disable=SC1090
[ -f "$STATE" ] && source "$STATE"
export AWS_REGION="${AWS_REGION:-us-east-1}"
export AWS_DEFAULT_REGION="$AWS_REGION"
LAB_NAME="${LAB_NAME:-meridian-lab}"
ROLE="${ROLE_NAME:-$LAB_NAME-imds-role}"

say() { printf '==> %s\n' "$*"; }

# Fall back to tag lookup if the state file is missing or incomplete.
if [ -z "${INSTANCE_ID:-}" ]; then
    INSTANCE_ID=$(aws ec2 describe-instances \
        --filters "Name=tag:Project,Values=$LAB_NAME" \
                  "Name=instance-state-name,Values=pending,running,stopping,stopped" \
        --query 'Reservations[].Instances[].InstanceId' --output text)
fi
if [ -z "${SG_ID:-}" ]; then
    SG_ID=$(aws ec2 describe-security-groups \
        --filters "Name=group-name,Values=$LAB_NAME-sg" \
        --query 'SecurityGroups[].GroupId' --output text)
fi

if [ -n "$INSTANCE_ID" ] && [ "$INSTANCE_ID" != "None" ]; then
    say "terminating $INSTANCE_ID"
    # shellcheck disable=SC2086
    aws ec2 terminate-instances --instance-ids $INSTANCE_ID >/dev/null
    # shellcheck disable=SC2086
    aws ec2 wait instance-terminated --instance-ids $INSTANCE_ID
fi

if [ -n "$SG_ID" ] && [ "$SG_ID" != "None" ]; then
    say "deleting security group $SG_ID"
    aws ec2 delete-security-group --group-id "$SG_ID"
fi

say "deleting key pair $LAB_NAME"
aws ec2 delete-key-pair --key-name "$LAB_NAME" 2>/dev/null

aws iam remove-role-from-instance-profile --instance-profile-name "$ROLE" --role-name "$ROLE" 2>/dev/null
aws iam delete-instance-profile --instance-profile-name "$ROLE" 2>/dev/null
if aws iam get-role --role-name "$ROLE" >/dev/null 2>&1; then
    say "deleting IAM role $ROLE"
    for p in $(aws iam list-attached-role-policies --role-name "$ROLE" \
                   --query 'AttachedPolicies[].PolicyArn' --output text); do
        aws iam detach-role-policy --role-name "$ROLE" --policy-arn "$p"
    done
    aws iam delete-role --role-name "$ROLE"
fi

rm -rf "$STATE_DIR"
say "done. If you created a DNS record for the lab, remove it too."
