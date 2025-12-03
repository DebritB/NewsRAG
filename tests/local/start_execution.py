"""
Manually triggers the NewsRAG-ETL-Workflow Step Function.
"""
import boto3
import json

# --- Configuration ---
# You can find this ARN in the AWS Step Functions console or in the CloudFormation stack outputs.
STATE_MACHINE_ARN = "arn:aws:states:us-east-1:536808117315:stateMachine:NewsRAG-ETL-Workflow"
# ---------------------

def start_state_machine():
    """Starts a new execution of the state machine."""
    print(f"Starting execution for State Machine: {STATE_MACHINE_ARN}")
    
    try:
        sfn_client = boto3.client('stepfunctions')
        
        response = sfn_client.start_execution(
            stateMachineArn=STATE_MACHINE_ARN,
            input=json.dumps({}) # Starting with an empty input
        )
        
        execution_arn = response['executionArn']
        print("\n✅ Execution started successfully!")
        print(f"   Execution ARN: {execution_arn}")
        
        # Provide a direct link to the AWS console for easy viewing
        region = STATE_MACHINE_ARN.split(':')[3]
        console_url = (
            f"https://{region}.console.aws.amazon.com/states/home"
            f"?region={region}#/executions/details/{execution_arn}"
        )
        print("\nTo view the execution in real-time, open this URL in your browser:")
        print(console_url)

    except Exception as e:
        print(f"\n❌ Error starting execution: {e}")

if __name__ == "__main__":
    start_state_machine()
