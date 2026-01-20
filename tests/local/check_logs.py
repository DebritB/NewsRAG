"""
Fetches the latest logs from a specific AWS CloudWatch log group.
Accepts a command-line argument to choose the Lambda function log.
Usage: python check_logs.py [1|2|3|4]
  1: Scraper
  2: Embedding Generator
  3: Index Manager
  4: Deduplicator
"""
import boto3
import time
import sys

# --- Configuration ---
LOG_GROUPS = {
    '1': '/aws/lambda/NewsRAG-Scraper',
    '2': '/aws/lambda/NewsRAG-EmbeddingGenerator',
    '3': '/aws/lambda/NewsRAG-IndexManager',
    '4': '/aws/lambda/NewsRAG-Deduplicator'
}
# ---------------------

def get_latest_logs(log_group_name):
    """Connects to CloudWatch and fetches the latest log events."""
    print(f"Connecting to CloudWatch log group: {log_group_name}...")
    
    try:
        client = boto3.client('logs')
        
        # Describe log streams to find the latest one
        response = client.describe_log_streams(
            logGroupName=log_group_name,
            orderBy='LastEventTime',
            descending=True,
            limit=1
        )
        
        if not response['logStreams']:
            print("❌ No log streams found for this function yet.")
            return
            
        latest_stream_name = response['logStreams'][0]['logStreamName']
        print(f"Found latest log stream: {latest_stream_name}")

        # Get log events from the latest stream
        print("\n--- Latest Logs ---")
        log_response = client.get_log_events(
            logGroupName=log_group_name,
            logStreamName=latest_stream_name,
            startFromHead=False, # Get latest events
            limit=50 # Get up to 50 latest log lines
        )
        
        if not log_response['events']:
            print("No new events found in the last few minutes.")
        
        for event in log_response['events']:
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(event['timestamp']/1000))
            message = event['message'].strip()
            print(f"[{timestamp}] {message}")
        
        print("-------------------\n")

    except client.exceptions.ResourceNotFoundException:
        print(f"❌ Error: Log group '{log_group_name}' not found.")
        print("   Please make sure the Lambda function has executed at least once.")
    except Exception as e:
        print(f"❌ An error occurred: {e}")

if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in LOG_GROUPS:
        print("Usage: python check_logs.py [1|2|3|4]")
        print("  1: Scraper")
        print("  2: Embedding Generator")
        print("  3: Index Manager")
        print("  4: Deduplicator")
        sys.exit(1)
        
    choice = sys.argv[1]
    selected_log_group = LOG_GROUPS[choice]
    get_latest_logs(selected_log_group)
