# Runbook

Operational procedures for Phase 0. Source of truth — keep current.

## Contents

1. [Tear down the ephemeral stack](#1-tear-down-the-ephemeral-stack-zero-per-hour-cost) (zero per-hour cost)
2. [Spin the stack back up later](#2-spin-the-stack-back-up-later) (full procedure including Cognito user re-create and re-seed)
3. [Truly zero cost: destroy bootstrap too](#3-truly-zero-cost-destroy-bootstrap-too) (rare; ~30 min of manual cleanup)
4. [Rotate the Anthropic API key](#4-rotate-the-anthropic-api-key)
5. [Re-seed without a full bring-up](#5-re-seed-without-a-full-bring-up)
6. [Deploy a backend code change](#6-deploy-a-backend-code-change)
7. [Deploy a frontend code change](#7-deploy-a-frontend-code-change)

---

## 1. Tear down the ephemeral stack (zero per-hour cost)

**Result:** RDS, Fargate, ALB, NAT GW, Cognito pool, SSM params, S3 raw + frontend buckets — all gone. Bootstrap layer (state bucket, ECR images, IAM roles, secret values, OIDC provider) stays. Per-hour AWS cost drops to **~$0**. Monthly cost remaining: **~$1-5** (bootstrap floor).

### Option A — from GitHub UI (no laptop AWS auth needed)

1. Open https://github.com/kanjilalanirban/Throughlin_TFE/actions/workflows/destroy.yml
2. Click **"Run workflow"** (top right)
3. In **"Type 'DESTROY' to confirm"**, type exactly: `DESTROY`
4. Click **"Run workflow"** (green button)
5. Wait ~5-10 minutes. The run completes when the page shows a green check.

### Option B — from your laptop

```bash
aws sso login --profile quantumsmartaws-admin
export AWS_PROFILE=quantumsmartaws-admin

cd Throughlin_TFE
make down
```

### Verify

```bash
# Should return DBInstanceNotFound
aws rds describe-db-instances \
  --profile quantumsmartaws-admin \
  --db-instance-identifier companybrain-phase0-pg 2>&1 | grep -E "DBInstanceNotFound|available"

# Should return INACTIVE
aws ecs describe-clusters \
  --profile quantumsmartaws-admin \
  --clusters companybrain-phase0-cluster \
  --query 'clusters[0].status' --output text 2>&1

# ECR images still there (bootstrap stays)
aws ecr describe-images \
  --profile quantumsmartaws-admin \
  --repository-name companybrain-backend \
  --query 'imageDetails[*].imageTags' --output json
```

---

## 2. Spin the stack back up later

**Time budget: ~15-20 minutes total** (Terraform apply + Cognito user + re-seed + frontend rebuild).

### Step 1: Re-create the ephemeral stack (~7-10 min)

**From GitHub UI:**
1. Open https://github.com/kanjilalanirban/Throughlin_TFE/actions/workflows/apply.yml
2. Click **"Run workflow"**
3. Type `APPLY`. Leave `backend_image_tag` as `latest`.
4. Click **"Run workflow"**.

**Or from laptop:**
```bash
cd Throughlin_TFE
aws sso login --profile quantumsmartaws-admin
export AWS_PROFILE=quantumsmartaws-admin
make up
```

The container's `entrypoint.sh` runs `alembic upgrade head` automatically on first boot. **The database is empty after this step** (just the schema).

### Step 2: Re-create the Cognito user (~30 sec)

The Cognito pool is in the ephemeral layer, so the `anirbank` user was destroyed. Re-create it (use whatever password you want — the old one is gone).

```bash
export AWS_PROFILE=quantumsmartaws-admin

POOL_ID=$(aws ssm get-parameter --name /companybrain/phase0/cognito/user_pool_id \
  --query Parameter.Value --output text)

aws cognito-idp admin-create-user \
  --user-pool-id "$POOL_ID" \
  --username anirbank \
  --user-attributes Name=email,Value=anirban.kanjilal@quantumsmart.com Name=email_verified,Value=true \
  --message-action SUPPRESS \
  --temporary-password 'TempP@ssw0rd1'

aws cognito-idp admin-set-user-password \
  --user-pool-id "$POOL_ID" \
  --username anirbank \
  --password 'YourPermanentP@ssw0rd!' \
  --permanent
```

Verify status is `CONFIRMED`:
```bash
aws cognito-idp admin-get-user --user-pool-id "$POOL_ID" --username anirbank \
  --query UserStatus --output text
```

### Step 3: Re-seed the database (~30-60 sec)

Migrations only created the schema. To populate the demo data (10 people, 3 initiatives, 2 decisions, 5 signals):

```bash
export AWS_PROFILE=quantumsmartaws-admin
cd Throughlin_app

# Pull current network config for ECS RunTask
SUBNETS=$(aws ecs describe-services --cluster companybrain-phase0-cluster \
  --services companybrain-phase0-api \
  --query 'services[0].networkConfiguration.awsvpcConfiguration.subnets' --output json)
SGS=$(aws ecs describe-services --cluster companybrain-phase0-cluster \
  --services companybrain-phase0-api \
  --query 'services[0].networkConfiguration.awsvpcConfiguration.securityGroups' --output json)

cat > /tmp/network.json <<EOF
{ "awsvpcConfiguration": { "subnets": $SUBNETS, "securityGroups": $SGS, "assignPublicIp": "DISABLED" } }
EOF

cat > /tmp/seed-overrides.json <<'EOF'
{ "containerOverrides": [{
    "name": "api",
    "command": ["python", "-m", "seed.load"],
    "environment": [
      {"name": "ENVIRONMENT", "value": "phase0"},
      {"name": "RUN_MIGRATIONS_ON_STARTUP", "value": "false"}
    ]
}] }
EOF

TASK=$(aws ecs run-task \
  --cluster companybrain-phase0-cluster \
  --task-definition companybrain-phase0-api \
  --launch-type FARGATE \
  --network-configuration file:///tmp/network.json \
  --overrides file:///tmp/seed-overrides.json \
  --query 'tasks[0].taskArn' --output text)

aws ecs wait tasks-stopped --cluster companybrain-phase0-cluster --tasks "$TASK"

# Confirm: exit code 0 means seed succeeded
aws ecs describe-tasks --cluster companybrain-phase0-cluster --tasks "$TASK" \
  --query 'tasks[0].containers[0].exitCode' --output text
```

If you want to also verify the row counts, run the count utility the same way with `command: ["python", "-m", "seed.count"]`. Should report:

```
people: 10
initiatives: 3
decisions: 2
signals: 5
person_initiative: 6
```

### Step 4: Rebuild + upload the frontend (~30-60 sec)

The frontend bundle has the previous stack's ALB URL + Cognito IDs baked in. Re-trigger the workflow to rebuild it against the current SSM values.

**From GitHub UI:**
1. https://github.com/kanjilalanirban/Throughlin_app/actions/workflows/frontend-deploy.yml
2. **Run workflow** → leave defaults → Run

**Or locally:**
```bash
cd Throughlin_app/frontend
API_URL=$(aws ssm get-parameter --profile quantumsmartaws-admin \
  --name /companybrain/phase0/alb/url --query Parameter.Value --output text)
POOL=$(aws ssm get-parameter --profile quantumsmartaws-admin \
  --name /companybrain/phase0/cognito/user_pool_id --query Parameter.Value --output text)
CLIENT=$(aws ssm get-parameter --profile quantumsmartaws-admin \
  --name /companybrain/phase0/cognito/client_id --query Parameter.Value --output text)
BUCKET=$(aws ssm get-parameter --profile quantumsmartaws-admin \
  --name /companybrain/phase0/s3/frontend_bucket --query Parameter.Value --output text)

VITE_API_URL="$API_URL" \
VITE_COGNITO_USER_POOL_ID="$POOL" \
VITE_COGNITO_CLIENT_ID="$CLIENT" \
VITE_AWS_REGION=ca-central-1 \
pnpm build

aws s3 sync dist/ "s3://$BUCKET/" --delete --profile quantumsmartaws-admin
```

### Step 5: Get the live URLs

```bash
aws ssm get-parameter --profile quantumsmartaws-admin \
  --name /companybrain/phase0/s3/frontend_url --query Parameter.Value --output text
aws ssm get-parameter --profile quantumsmartaws-admin \
  --name /companybrain/phase0/alb/url --query Parameter.Value --output text
```

Open the frontend URL in a browser. Sign in with `anirbank` and the password from Step 2.

---

## 3. Truly zero cost: destroy bootstrap too

You almost never want this — it removes the ability to spin back up without redoing the manual bootstrap. Do it only if you're winding the project down or moving accounts.

```bash
export AWS_PROFILE=quantumsmartaws-admin

# 1. Tear down ephemeral first (see procedure 1)

# 2. Empty + delete ECR repos (Terraform won't delete non-empty repos)
for repo in companybrain-backend companybrain-jira-ingester companybrain-github-ingester \
            companybrain-hris-ingester companybrain-normalizer; do
  IMAGES=$(aws ecr list-images --repository-name "$repo" --query 'imageIds[*]' --output json)
  if [ "$IMAGES" != "[]" ]; then
    aws ecr batch-delete-image --repository-name "$repo" --image-ids "$IMAGES"
  fi
done

# 3. Force-delete secrets (skip 7-day recovery window)
for s in anthropic/api-key jira/oauth-client github/app-key; do
  aws secretsmanager delete-secret \
    --secret-id "companybrain/phase0/$s" \
    --force-delete-without-recovery
done

# 4. Remove `prevent_destroy = true` from infra/bootstrap/tf-state-bucket.tf
#    (Terraform refuses to destroy state bucket + lock table otherwise)
sed -i.bak 's/prevent_destroy = true/prevent_destroy = false/g' \
  Throughlin_TFE/infra/bootstrap/tf-state-bucket.tf

# 5. Destroy bootstrap
cd Throughlin_TFE/infra/bootstrap
terraform destroy -auto-approve

# 6. (Optional) Manually empty the state bucket if Terraform refuses
aws s3 rm s3://companybrain-tf-state --recursive
aws s3api delete-bucket --bucket companybrain-tf-state
```

After this the AWS account has zero project resources. The GitHub Secrets and the IAM Identity Center user remain.

---

## 4. Rotate the Anthropic API key

The Anthropic secret value persists across `make down` / `make up` cycles because the secret container is in the bootstrap layer.

```bash
export AWS_PROFILE=quantumsmartaws-admin

aws secretsmanager put-secret-value \
  --secret-id companybrain/phase0/anthropic/api-key \
  --secret-string 'sk-ant-...new-key...'
```

If the stack is currently up, force a new ECS deployment so the running task re-fetches:

```bash
aws ecs update-service \
  --cluster companybrain-phase0-cluster \
  --service companybrain-phase0-api \
  --force-new-deployment
```

---

## 5. Re-seed without a full bring-up

Use the ECS RunTask pattern in Step 3 of procedure 2. The seed loader wipes existing rows first, so re-running it gives you the original 10/3/2/5/6 fixture state.

---

## 6. Deploy a backend code change

Push to `main` with any change under `backend/**` — the [`backend-image.yml`](.github/workflows/backend-image.yml) workflow auto-triggers:

1. Builds the multi-stage Docker image (linux/amd64)
2. Pushes to ECR as `:latest` + `:sha-<short>`
3. If the ephemeral stack is up, force-redeploys the ECS service (~60s to swap to the new task)
4. If the stack is down, the image waits in ECR for the next `make up`

To trigger manually without a code change: Actions → "Backend image" → Run workflow.

---

## 7. Deploy a frontend code change

Push to `main` with any change under `frontend/**` — the [`frontend-deploy.yml`](.github/workflows/frontend-deploy.yml) workflow auto-triggers:

1. Reads current ALB URL + Cognito IDs from SSM
2. Builds with those baked in as `VITE_*` env vars
3. `aws s3 sync` to the frontend bucket
4. Skip-with-warning if the ephemeral stack is currently down

To trigger manually (e.g., to rebuild the bundle against a freshly-applied stack): Actions → "Frontend deploy" → Run workflow.
