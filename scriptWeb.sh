#!/bin/bash
set -euo pipefail

# 1) Install Docker
sudo dnf install -y docker

# 2) Enable & start the Docker daemon
sudo systemctl enable --now docker

# 3) Allow ec2-user to run Docker without sudo
sudo usermod -aG docker ec2-user

# ----- login to ECR -----
REGION="eu-north-1"
ACCOUNT="545581984870"            # replace once, or hard-code
sudo docker login -u AWS -p $(aws ecr get-login-password --region $REGION) $ACCOUNT.dkr.ecr.$REGION.amazonaws.com
# ----- pull and run container -----
IMAGE="$ACCOUNT.dkr.ecr.$REGION.amazonaws.com/crawler-web:latest"
sudo docker pull $IMAGE

cat >/home/ec2-user/env.list <<'EOF'
REDIS_HOST=master.web-crawler-redis.qrk9bb.eun1.cache.amazonaws.com
S3_BUCKET=web-crawler-datahoss
OPENSEARCH_HOST=vpc-web-crawler-domain-qmmwp5s2msg7wysupr52htm2hm.eu-north-1.es.amazonaws.com
SQS_QUEUE_URL=https://sqs.eu-north-1.amazonaws.com/545581984870/crawler
AWS_REGION=eu-north-1
MASTER_URL=http://172.31.29.141:6000
SQS_INDEXER_QUEUE_URL=https://sqs.eu-north-1.amazonaws.com/545581984870/indexer
EOF

# Map port 80 only for the web service
sudo docker run -d --name web --env-file /home/ec2-user/env.list -p 80:5000 $IMAGE