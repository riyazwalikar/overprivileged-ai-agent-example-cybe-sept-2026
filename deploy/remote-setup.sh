#!/usr/bin/env bash
# Runs on the EC2 instance (as ec2-user). Called by deploy.sh; not meant to be run by hand.
# Installs Docker + Compose + buildx (+ Caddy if DOMAIN is set) and starts the lab.
set -euo pipefail

DOMAIN="${DOMAIN:-}"
CADDY_VERSION=2.11.4
ARCH=$(uname -m)                       # x86_64 or aarch64
GOARCH=$([ "$ARCH" = aarch64 ] && echo arm64 || echo amd64)

sudo dnf install -y -q docker make jq nmap-ncat tar

# Compose and buildx are not packaged for AL2023; pull the plugin binaries.
PLUGINS=/usr/local/lib/docker/cli-plugins
sudo mkdir -p "$PLUGINS"
sudo curl -fsSL -o "$PLUGINS/docker-compose" \
    "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-$ARCH"
BUILDX=$(curl -fsSL https://api.github.com/repos/docker/buildx/releases/latest | jq -r .tag_name)
sudo curl -fsSL -o "$PLUGINS/docker-buildx" \
    "https://github.com/docker/buildx/releases/download/$BUILDX/buildx-$BUILDX.linux-$GOARCH"
sudo chmod +x "$PLUGINS"/*

sudo systemctl enable --now docker
sudo usermod -aG docker ec2-user

rm -rf ~/meridian-space-tours
tar -xzf ~/app.tgz -C ~ && rm ~/app.tgz
cd ~/meridian-space-tours
# On EC2 the instance role is used; no named profile.
sed -i 's/^AWS_PROFILE=.*/AWS_PROFILE=/' .env
mkdir -p ~/.aws

# New group membership is not active in this session yet, so use sudo.
sudo docker compose up -d --build --wait

if [ -n "$DOMAIN" ]; then
    curl -fsSL "https://github.com/caddyserver/caddy/releases/download/v$CADDY_VERSION/caddy_${CADDY_VERSION}_linux_$GOARCH.tar.gz" \
        | sudo tar -xz -C /usr/local/bin caddy
    sudo mkdir -p /etc/caddy
    printf '%s {\n\treverse_proxy localhost:8000\n}\n' "$DOMAIN" | sudo tee /etc/caddy/Caddyfile >/dev/null
    sudo tee /etc/systemd/system/caddy.service >/dev/null <<'EOF'
[Unit]
Description=Caddy
After=network-online.target
Wants=network-online.target

[Service]
ExecStart=/usr/local/bin/caddy run --config /etc/caddy/Caddyfile
ExecReload=/usr/local/bin/caddy reload --config /etc/caddy/Caddyfile
Environment=XDG_DATA_HOME=/var/lib XDG_CONFIG_HOME=/etc
Restart=on-failure
AmbientCapabilities=CAP_NET_BIND_SERVICE

[Install]
WantedBy=multi-user.target
EOF
    sudo systemctl daemon-reload
    sudo systemctl enable --now caddy
fi

sudo docker compose ps
