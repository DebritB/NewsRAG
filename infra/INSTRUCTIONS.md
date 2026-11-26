# NewsRAG — AWS Setup Instructions

Everything needed to build the NewsRAG cloud setup from an empty AWS account.
Region for everything: **Asia Pacific (Sydney) `ap-southeast-2`**.

> Before creating anything in the console, check the region selector in the top bar says **Sydney**.
> AWS resources live in the region they were created in.

## Overview

| What | Created by | Where |
|---|---|---|
| Your console login | AWS Builder ID (Google sign-in) | AWS |
| Budget alert | Manual (console) | AWS Billing |
| GitHub OIDC provider, deploy role, artifact S3 bucket | `infra/bootstrap.yaml` (run once by hand) | AWS |
| Bedrock model access | Manual (console) | AWS Bedrock |
| Lambdas, Step Function, schedule, Lambda IAM roles | `template.yaml` (deployed by GitHub Actions) | AWS |
| Database + vector search | Manual | MongoDB Atlas |
| Deploy settings | Manual | GitHub repo settings |
| Dashboard | Manual | Streamlit |

No AWS access keys are created anywhere:
- You sign in with your Builder ID.
- GitHub Actions gets temporary credentials through OIDC on every run.
- Lambdas get credentials from their IAM roles automatically.

---

## Phase 1 — Account basics (one time)

1. Sign in: go to the AWS sign-ins page and click **Sign in** on **NewsRAG-V2** (Google / Builder ID login).
2. Protect the login: account menu (top right) → **Profile** → **Security**:
   - **Register device** under MFA (authenticator app or passkey)
   - **Add recovery email**
3. Budget alert: search **Budgets** → **Create budget** → **Monthly cost budget** → set an amount below the remaining credits, with email alerts at roughly 50% and 80%.
4. Set the console region to **Sydney (ap-southeast-2)**.

**Free plan notes**
- Credits and days remaining are shown in the account menu (top right). When either runs out the account must be upgraded to a paid plan to keep running.
- Check **Billing → Credits** to see which services the credits cover. Claude (Anthropic) on Bedrock may be billed separately from credits.

---

## Phase 2 — Bootstrap stack (one time)

Creates the GitHub OIDC provider, the `github-newsrag-deploy` role (only `main` in `DebritB/NewsRAG` can use it) and the S3 bucket for deploy artifacts (old files auto-deleted after 30 days).

This step must be done by hand: GitHub can't create the role it needs to sign in.

### Option A — CloudShell (recommended)

1. Click the `>_` icon in the console top bar to open **CloudShell** (region: Sydney).
2. **Actions** → **Upload file** → `infra/bootstrap.yaml`.
3. Deploy:
   ```bash
   aws cloudformation deploy \
     --template-file bootstrap.yaml \
     --stack-name newsrag-bootstrap \
     --capabilities CAPABILITY_NAMED_IAM \
     --region ap-southeast-2
   ```
4. Print the outputs:
   ```bash
   aws cloudformation describe-stacks \
     --stack-name newsrag-bootstrap \
     --region ap-southeast-2 \
     --query "Stacks[0].Outputs" \
     --output table
   ```
5. Save `DeployRoleArn` and `ArtifactBucketName` for Phase 4.

### Option B — Console

1. **CloudFormation** → **Create stack** → **With new resources (standard)**
2. **Choose an existing template** → **Upload a template file** → `infra/bootstrap.yaml` → **Next**
3. Stack name `newsrag-bootstrap` → keep parameters (`DebritB/NewsRAG`, `main`) → **Next** → **Next**
4. Tick **"I acknowledge that AWS CloudFormation might create IAM resources with custom names"** → **Submit**
5. Wait for `CREATE_COMPLETE` → **Outputs** tab → copy `DeployRoleArn` and `ArtifactBucketName`

### If it fails

```bash
aws cloudformation describe-stack-events --stack-name newsrag-bootstrap --region ap-southeast-2 \
  --query "StackEvents[?contains(ResourceStatus,'FAILED')].[LogicalResourceId,ResourceStatusReason]" \
  --output table
```
A stack stuck in `ROLLBACK_COMPLETE` must be deleted before trying again:
```bash
aws cloudformation delete-stack --stack-name newsrag-bootstrap --region ap-southeast-2
```

### Updating it later

Edit `infra/bootstrap.yaml`, upload it to CloudShell again and rerun the deploy command from step 3. CloudFormation updates the stack in place.

---

## Phase 3 — Bedrock models (one time)

Console (region: Sydney) → **Bedrock** → **Model catalog**:

1. **Amazon Titan Text Embeddings V2** (`amazon.titan-embed-text-v2:0`)
   - Used for all embeddings. The vector index (`vector_search_index_config.json`) is built for its 1024-dimension output.
   - If it is **not available in Sydney**: keep only the embedding calls on `us-east-1` (Bedrock can be called cross-region) rather than switching embedding models, which would require a new index and re-embedding every article.
2. **A Claude model** (Haiku-class is cheapest)
   - Used by the scraper (classifying low-confidence articles) and the chatbot (answers).
   - In Sydney it may only be available through a cross-region inference profile (ID starting `au.anthropic.` or `apac.anthropic.`). Note the exact ID.
3. If a model shows **Request access** / **Enable**, do it. Anthropic models may ask for a short use-case form.

The model IDs go into the code in Phase 5.

---

## Phase 4 — MongoDB Atlas and GitHub (one time)

### MongoDB Atlas
1. If creating a new free (M0) cluster, choose **AWS / Sydney (ap-southeast-2)** to match the Lambdas.
2. **Network Access** → **Add IP Address** → `0.0.0.0/0` (Lambdas have no fixed IP).
3. Copy the connection string (database user with read/write on `news_rag`).
4. The vector search index is created automatically by `IndexManagerFunction` on the first pipeline run.

### GitHub
Repo → **Settings** → **Secrets and variables** → **Actions**:

| Type | Name | Value |
|---|---|---|
| Variable | `AWS_ROLE_ARN` | `DeployRoleArn` from Phase 2 |
| Secret | `S3_BUCKET_NAME` | `ArtifactBucketName` from Phase 2 |
| Secret | `MONGODB_CONNECTION_STRING` | Atlas connection string |

Delete any old `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` secrets.

---

## Phase 5 — Code changes before the first deploy

- [ ] `.github/workflows/deploy.yml` → OIDC instead of access keys:
  ```yaml
  jobs:
    deploy:
      runs-on: ubuntu-latest
      permissions:
        id-token: write
        contents: read
      steps:
        - name: Checkout repository
          uses: actions/checkout@v4

        - name: Configure AWS credentials
          uses: aws-actions/configure-aws-credentials@v4
          with:
            role-to-assume: ${{ vars.AWS_ROLE_ARN }}
            aws-region: ap-southeast-2
  ```
- [ ] Region: replace hard-coded `us-east-1` with `os.environ["AWS_REGION"]` (Lambda sets it automatically) in
  `chatbot_lambda.py`, `embedding_lambda.py`, `lambda_function.py`, `bedrock_embeddings.py`
- [ ] Claude model ID from Phase 3 in `chatbot_lambda.py` and `bedrock_embeddings.py`
- [ ] Matching Bedrock IAM ARNs in `template.yaml` (inference profiles need both the inference-profile ARN and the foundation-model ARNs)
- [ ] Chatbot public URL: add `FunctionUrlConfig` to `ChatbotFunction` in `template.yaml`, plus an output for the URL
- [ ] `tests/local/start_execution.py`: remove the hard-coded state machine ARN from the old account

Recommended (saves credits and deploy time):
- [ ] Schedule in `template.yaml`: `rate(2 hours)` → `rate(12 hours)`
- [ ] Remove Step 6 of `.github/workflows/deploy.sh` (triggers the full pipeline on every push)
- [ ] Remove `langchain`, `langchain-aws`, `boto3` from `requirements-lambda.txt` (not used; boto3 is in the Lambda runtime)
- [ ] Remove the `pip install awscli` step from `deploy.yml` (already on the runner)
- [ ] Stop tracking `lambda_package/` in git: `git rm -r --cached lambda_package` and add it to `.gitignore`

---

## Phase 6 — First deploy

1. Push to `main`.
2. Watch GitHub → **Actions**. The first run creates the `newsrag-stack` stack.
3. Common errors:

| Error | Cause | Fix |
|---|---|---|
| `Not authorized to perform sts:AssumeRoleWithWebIdentity` | Trust policy doesn't match | Check repo name / branch in `bootstrap.yaml`; check `AWS_ROLE_ARN` |
| `AccessDenied` on a specific action | Deploy role missing a permission | Add it to the role in `bootstrap.yaml` and redeploy Phase 2 |
| Bedrock `AccessDeniedException` at runtime | Model not enabled, or IAM ARN doesn't match the model / inference profile | Phase 3, then fix ARNs in `template.yaml` |
| Lambda can't connect to MongoDB | Atlas network access | Phase 4 — `0.0.0.0/0` |

---

## Phase 7 — After the first deploy

1. Get the chatbot URL from the stack outputs:
   ```bash
   aws cloudformation describe-stacks --stack-name newsrag-stack --region ap-southeast-2 \
     --query "Stacks[0].Outputs" --output table
   ```
2. Streamlit app → **Settings** → **Secrets**: set `AWS_API_URL` to the chatbot URL, and `MONGODB_URI` to the Atlas connection string.
3. Start the pipeline once by hand (Step Functions → `NewsRAG-ETL-Workflow` → **Start execution**), or wait for the schedule.
4. After a day, check **Billing → Cost Explorer** for the real cost per run.

---

## Later

- Narrow the deploy role: replace `AdministratorAccess` in `bootstrap.yaml` with only what the deploy needs (CloudFormation, S3, Lambda, IAM, Step Functions, EventBridge, CloudWatch Logs), then redeploy Phase 2.
- Changing region: deploy Phase 2 and the main stack in the new region, update the GitHub variable/secret and Streamlit URL, then delete the old stacks. Data is safe in Atlas.
- Before the free plan ends: upgrade to a paid plan or the account stops.
