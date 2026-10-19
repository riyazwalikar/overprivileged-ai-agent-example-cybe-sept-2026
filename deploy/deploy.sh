#!/usr/bin/env bash
# Deploy the Meridian Space Tours lab to a single EC2 instance.
#
# Creates (all tagged Project=$LAB_NAME):
#   - SSH key pair       (private key saved to deploy/.state/)
#   - security group     (22 + 8000 open to ALLOW_CIDR; 80/443 too if DOMAIN set)
#   - IAM role + instance profile with EC2/S3/IAM FullAccess  <-- deliberately overprivileged
#   - t3.small Amazon Linux 2023 instance in the default VPC
# Then copies the app over SSH, installs Docker, and starts the stack.
#
# Usage:
#   AWS_PROFILE=lab ./deploy/deploy.sh
#   AWS_PROFILE=lab DOMAIN=chat.example.com ./deploy/deploy.sh
#
# Undo everything with ./deploy/teardown.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP="$ROOT/meridian-space-tours"
STATE_DIR="$ROOT/deploy/.state"
STATE="$STATE_DIR/state.env"

export AWS_REGION="${AWS_REGION:-us-east-1}"
export AWS_DEFAULT_REGION="$AWS_REGION"
LAB_NAME="${LAB_NAME:-meridian-lab}"
INSTANCE_TYPE="${INSTANCE_TYPE:-t3.small}"
DOMAIN="${DOMAIN:-}"
ROLE="$LAB_NAME-imds-role"
POLICIES=(
    arn:aws:iam::aws:policy/AmazonEC2FullAccess
    arn:aws:iam::aws:policy/AmazonS3FullAccess
    arn:aws:iam::aws:policy/IAMFullAccess
)
TAGS="Key=Project,Value=$LAB_NAME"

say() { printf '==> %s\n' "$*"; }
die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

# ---- preflight ----
for bin in aws ssh scp tar curl; do
    command -v "$bin" >/dev/null || die "$bin not found"
done
[ -f "$STATE" ] && die "existing deployment found ($STATE). Run ./deploy/teardown.sh first."

if [ ! -f "$APP/.env" ]; then
    "$APP/scripts/gen_env.sh"
    die "generated $APP/.env — set LLM_API_KEY in it, then re-run"
fi
grep -q '^LLM_API_KEY=sk-your-key-here' "$APP/.env" && die "set LLM_API_KEY in $APP/.env"

ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
MY_IP=$(curl -fsS https://checkip.amazonaws.com | tr -d '[:space:]')
ALLOW_CIDR="${ALLOW_CIDR:-$MY_IP/32}"
say "account $ACCOUNT, region $AWS_REGION, allowing $ALLOW_CIDR"

mkdir -p "$STATE_DIR"
{
    echo "AWS_REGION=$AWS_REGION"
    echo "LAB_NAME=$LAB_NAME"
} > "$STATE"

# ---- key pair ----
KEY="$STATE_DIR/$LAB_NAME.pem"
say "creating key pair $LAB_NAME"
aws ec2 create-key-pair --key-name "$LAB_NAME" \
    --tag-specifications "ResourceType=key-pair,Tags=[{$TAGS}]" \
    --query KeyMaterial --output text > "$KEY"
chmod 600 "$KEY"
echo "KEY_NAME=$LAB_NAME" >> "$STATE"

# ---- security group ----
VPC=$(aws ec2 describe-vpcs --filters Name=is-default,Values=true \
    --query 'Vpcs[0].VpcId' --output text)
[ "$VPC" = "None" ] && die "no default VPC in $AWS_REGION"

say "creating security group in $VPC"
SG=$(aws ec2 create-security-group --group-name "$LAB_NAME-sg" \
    --description "Meridian lab - live RCE, keep locked down" --vpc-id "$VPC" \
    --tag-specifications "ResourceType=security-group,Tags=[{$TAGS}]" \
    --query GroupId --output text)
echo "SG_ID=$SG" >> "$STATE"

open_port() {
    aws ec2 authorize-security-group-ingress --group-id "$SG" \
        --protocol tcp --port "$1" --cidr "$2" >/dev/null
}
open_port 22 "$ALLOW_CIDR"
open_port 8000 "$ALLOW_CIDR"
if [ -n "$DOMAIN" ]; then
    open_port 80 0.0.0.0/0   # Let's Encrypt HTTP-01 challenge
    open_port 443 "$ALLOW_CIDR"
fi

# ---- IAM role (the overprivileged bit) ----
say "creating IAM role $ROLE (EC2/S3/IAM FullAccess)"
aws iam create-role --role-name "$ROLE" --tags "$TAGS" \
    --assume-role-policy-document '{
      "Version": "2012-10-17",
      "Statement": [{"Effect": "Allow", "Principal": {"Service": "ec2.amazonaws.com"}, "Action": "sts:AssumeRole"}]
    }' >/dev/null
echo "ROLE_NAME=$ROLE" >> "$STATE"
for p in "${POLICIES[@]}"; do
    aws iam attach-role-policy --role-name "$ROLE" --policy-arn "$p"
done
aws iam create-instance-profile --instance-profile-name "$ROLE" --tags "$TAGS" >/dev/null
aws iam add-role-to-instance-profile --instance-profile-name "$ROLE" --role-name "$ROLE"

# ---- instance ----
AMI=$(aws ssm get-parameter \
    --name /aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64 \
    --query Parameter.Value --output text)

say "launching $INSTANCE_TYPE ($AMI)"
# New instance profiles take a few seconds to become usable.
for i in $(seq 1 12); do
    if INSTANCE=$(aws ec2 run-instances --image-id "$AMI" --instance-type "$INSTANCE_TYPE" \
        --key-name "$LAB_NAME" --security-group-ids "$SG" \
        --iam-instance-profile Name="$ROLE" \
        --metadata-options HttpTokens=required,HttpPutResponseHopLimit=2,HttpEndpoint=enabled \
        --block-device-mappings 'DeviceName=/dev/xvda,Ebs={VolumeSize=20,VolumeType=gp3}' \
        --tag-specifications "ResourceType=instance,Tags=[{$TAGS},{Key=Name,Value=$LAB_NAME}]" \
        --query 'Instances[0].InstanceId' --output text 2>/dev/null); then
        break
    fi
    [ "$i" = 12 ] && die "run-instances kept failing (instance profile not ready?)"
    sleep 5
done
echo "INSTANCE_ID=$INSTANCE" >> "$STATE"

aws ec2 wait instance-running --instance-ids "$INSTANCE"
IP=$(aws ec2 describe-instances --instance-ids "$INSTANCE" \
    --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)
echo "PUBLIC_IP=$IP" >> "$STATE"
say "instance $INSTANCE up at $IP"

SSH_OPTS=(-i "$KEY" -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile="$STATE_DIR/known_hosts" -o ConnectTimeout=5)
say "waiting for SSH"
for i in $(seq 1 30); do
    ssh "${SSH_OPTS[@]}" "ec2-user@$IP" true 2>/dev/null && break
    [ "$i" = 30 ] && die "SSH never came up"
    sleep 5
done

# ---- ship the app ----
say "copying app"
COPYFILE_DISABLE=1 tar -C "$ROOT" -czf "$STATE_DIR/app.tgz" \
    --exclude='docs' --exclude='__pycache__' --exclude='.DS_Store' \
    --exclude='walkthrough.md' --exclude='inputs-demo.md' --exclude='creds.md' \
    meridian-space-tours
scp "${SSH_OPTS[@]}" "$STATE_DIR/app.tgz" "$ROOT/deploy/remote-setup.sh" "ec2-user@$IP:"
rm -f "$STATE_DIR/app.tgz"

say "installing Docker and starting the stack (takes a few minutes)"
# shellcheck disable=SC2029  # DOMAIN is ours and deliberately expands client-side
ssh "${SSH_OPTS[@]}" "ec2-user@$IP" "DOMAIN='$DOMAIN' bash remote-setup.sh"

# ---- done ----
PW=$(cat "$APP/secrets/basic_auth_password" 2>/dev/null || true)
URL="http://$IP:8000"
[ -n "$DOMAIN" ] && URL="https://$DOMAIN"

cat <<EOF

Lab is up.

  URL:      $URL
  Login:    comet / ${PW:-<no password set>}
  SSH:      ssh -i $KEY ec2-user@$IP
  Allowed:  $ALLOW_CIDR

EOF
[ -n "$DOMAIN" ] && echo "  Point an A record for $DOMAIN at $IP (Caddy fetches the cert once DNS resolves)."
echo "  The instance role is EC2/S3/IAM FullAccess. Tear down when done: ./deploy/teardown.sh"
