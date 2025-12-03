# Deploy NewsRAG Lambda Function to AWS
# This script packages and deploys the Lambda function using CloudFormation CLI

Write-Host "Starting deployment process..." -ForegroundColor Cyan

# Step 1: Create deployment package directory
Write-Host "`n[1/5] Creating deployment package..." -ForegroundColor Yellow
$packageDir = "lambda_package"
if (Test-Path $packageDir) {
    Remove-Item -Recurse -Force $packageDir
}
New-Item -ItemType Directory -Path $packageDir | Out-Null

# Step 2: Copy Lambda code and dependencies
Write-Host "[2/5] Copying Lambda function code and configs..." -ForegroundColor Yellow
Copy-Item -Path "lambda_function.py" -Destination $packageDir
Copy-Item -Path "embedding_lambda.py" -Destination $packageDir
Copy-Item -Path "index_manager_lambda.py" -Destination $packageDir
Copy-Item -Path "deduplicator_lambda.py" -Destination $packageDir
Copy-Item -Path "scrape_news.py" -Destination $packageDir
Copy-Item -Path "bedrock_embeddings.py" -Destination $packageDir
Copy-Item -Path "keyword_classifier.py" -Destination $packageDir
Copy-Item -Path "vector_search_index_config.json" -Destination $packageDir
Copy-Item -Path "scrapers" -Destination $packageDir -Recurse
Copy-Item -Path "models" -Destination $packageDir -Recurse

# Step 3: Install dependencies
Write-Host "[3/5] Installing dependencies..." -ForegroundColor Yellow
pip install -r requirements-lambda.txt -t $packageDir --upgrade

# Step 4: Package with CloudFormation
Write-Host "[4/5] Packaging with CloudFormation..." -ForegroundColor Yellow
python -m awscli cloudformation package `
    --template-file template.yaml `
    --s3-bucket newsrag-deployment-536808117315 `
    --output-template-file packaged-template.yaml

if ($LASTEXITCODE -ne 0) {
    Write-Host "Packaging failed!" -ForegroundColor Red
    exit 1
}

# Step 5: Deploy with CloudFormation
Write-Host "[5/5] Deploying to AWS..." -ForegroundColor Yellow

# Check if the environment variable is set
if (-not $env:MONGODB_CONNECTION_STRING) {
    Write-Host "Error: MONGODB_CONNECTION_STRING environment variable is not set." -ForegroundColor Red
    Write-Host "Please set it before running this script." -ForegroundColor Red
    exit 1
}

python -m awscli cloudformation deploy `
    --template-file packaged-template.yaml `
    --stack-name newsrag-stack `
    --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM `
    --parameter-overrides `
        MongoDBConnectionString=$env:MONGODB_CONNECTION_STRING

if ($LASTEXITCODE -eq 0) {
    Write-Host "`nDeployment successful! " -ForegroundColor Green
    Write-Host "Lambda function updated in AWS." -ForegroundColor Green
} else {
    Write-Host "`nDeployment failed!" -ForegroundColor Red
    exit 1
}
