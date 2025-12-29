#!/bin/bash
set -eux
dnf update -y
dnf install -y git docker
# Install Docker + Compose plugin
# amazon-linux-extras enable docker || true
systemctl enable --now docker
usermod -aG docker ec2-user
curl -SL https://github.com/docker/compose/releases/download/v2.24.7/docker-compose-linux-x86_64 \
  -o /usr/local/bin/docker-compose && chmod +x /usr/local/bin/docker-compose

# Get repo
su - ec2-user -c "git clone https://github.com/barrynalex/Crypto_trade_monitor.git"
cd /home/ec2-user/Crypto_trade_monitor

# 取得 AWS Public IP
TOKEN=`curl -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600"`
PUBLIC_IP=`curl -H "X-aws-ec2-metadata-token: $TOKEN" -v http://169.254.169.254/latest/meta-data/public-ipv4`

# 建立 .env 檔案，讓 docker-compose 讀取
echo "EC2_PUBLIC_IP=$PUBLIC_IP" > /home/ec2-user/Crypto_trade_monitor/.env

# Optional: pull env/creds from SSM or Secrets Manager here
# Run stack
sudo -u ec2-user make start