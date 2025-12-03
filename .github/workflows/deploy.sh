#!/bin/bash
# Exit immediately if a command exits with a non-zero status.
set -e

echo "Starting deployment process..."

# Step 1: Create deployment package directory
echo "Step 1/5: Creating deployment package..."
PACKAGE_DIR="lambda_package"
rm -rf $PACKAGE_DIR
mkdir $PACKAGE_DIR

# Step 2: Copy Lambda code and dependencies
echo "Step 2/5: Copying Lambda function code and configs..."
cp lambda_function.py $PACKAGE_DIR/
cp embedding_lambda.py $PACKAGE_DIR/
cp index_manager_lambda.py $PACKAGE_DIR/
cp deduplicator_lambda.py $PACKAGE_DIR/
cp scrape_news.py $PACKAGE_DIR/
cp bedrock_embeddings.py $PACKAGE_DIR/
cp keyword_classifier.py $PACKAGE_DIR/
cp vector_search_index_config.json $PACKAGE_DIR/
cp -r scrapers $PACKAGE_DIR/
cp -r models $PACKAGE_DIR/

# Step 3: Install dependencies
echo "Step 3/5: Installing dependencies..."
pip install -r requirements-lambda.txt -t $PACKAGE_DIR --upgrade

# Step 4: Package with CloudFormation
echo "Step 4/5: Packaging with CloudFormation..."
aws cloudformation package \
    --template-file template.yaml \
    --s3-bucket "$S3_BUCKET_NAME" \
    --output-template-file packaged-template.yaml

# Step 5: Deploy with CloudFormation
echo "Step 5/5: Deploying to AWS..."
aws cloudformation deploy \
    --template-file packaged-template.yaml \
    --stack-name newsrag-stack \
    --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM \
    --parameter-overrides \
        MongoDBConnectionString="$MONGODB_CONNECTION_STRING"

echo "Deployment successful!"
