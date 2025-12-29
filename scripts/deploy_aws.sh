#!/bin/bash
set -eux
dnf update -y
dnf install -y git python3
# Install Docker + Compose plugin
amazon-linux-extras enable docker || true
dnf install -y docker
systemctl enable --now docker
usermod -aG docker ec2-user
curl -SL https://github.com/docker/compose/releases/download/v2.24.7/docker-compose-linux-x86_64 \
  -o /usr/local/bin/docker-compose && chmod +x /usr/local/bin/docker-compose

# Get repo
su - ec2-user -c "git clone https://github.com/<your-org>/crypto_trade_monitor.git"
cd /home/ec2-user/crypto_trade_monitor

# Optional: pull env/creds from SSM or Secrets Manager here
# Run stack
sudo -u ec2-user make start