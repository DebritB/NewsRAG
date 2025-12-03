"""
Manually invoke the NewsRAG-Scraper Lambda function
"""
import boto3
import json

LAMBDA_FUNCTION_NAME = 'NewsRAG-Scraper'

def invoke_lambda():
    """Invokes the Lambda function"""
    try:
        print(f"Invoking Lambda function: {LAMBDA_FUNCTION_NAME}...")
        lambda_client = boto3.client('lambda')
        
        response = lambda_client.invoke(
            FunctionName=LAMBDA_FUNCTION_NAME,
            InvocationType='RequestResponse' # Can be 'Event' for async
        )
        
        print("Lambda invoked successfully. Waiting for response...")
        
        # The response payload is a streaming body, so we need to read and decode it
        response_payload = json.load(response['Payload'])
        
        print("\n----- Lambda Response -----")
        print(json.dumps(response_payload, indent=2))
        print("-------------------------\n")

        # Check the status code from the Lambda's return value
        if response_payload.get('statusCode') == 200:
            print("✅ Lambda executed successfully.")
        else:
            print("❌ Lambda execution resulted in an error.")

    except Exception as e:
        print(f"❌ Error invoking Lambda function: {e}")

if __name__ == "__main__":
    invoke_lambda()
