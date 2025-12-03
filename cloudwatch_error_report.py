import boto3
from datetime import datetime, timedelta, timezone

# List of NewsRAG Lambda log groups
LOG_GROUPS = [
    '/aws/lambda/NewsRAG-Scraper',
    '/aws/lambda/NewsRAG-EmbeddingGenerator',
    '/aws/lambda/NewsRAG-IndexManager',
    '/aws/lambda/NewsRAG-Deduplicator',
]

ERROR_KEYWORDS = ['ERROR', 'Exception', 'Traceback', '❌', 'Failed']

def fetch_errors(log_group, start_time):
    client = boto3.client('logs')
    errors = []
    streams = client.describe_log_streams(logGroupName=log_group, orderBy='LastEventTime', descending=True)['logStreams']
    for stream in streams:
        stream_name = stream['logStreamName']
        events = client.get_log_events(
            logGroupName=log_group,
            logStreamName=stream_name,
            startTime=int(start_time.timestamp() * 1000),
            endTime=int(datetime.now(timezone.utc).timestamp() * 1000),
            startFromHead=True
        )['events']
        for event in events:
            msg = event['message']
            if any(keyword in msg for keyword in ERROR_KEYWORDS):
                errors.append({
                    'timestamp': datetime.fromtimestamp(event['timestamp']/1000, tz=timezone.utc).isoformat(),
                    'log_group': log_group,
                    'stream': stream_name,
                    'message': msg.strip()
                })
    return errors

def main():
    start_time = datetime.now(timezone.utc) - timedelta(days=3)
    all_errors = []
    for log_group in LOG_GROUPS:
        print(f'Checking {log_group}...')
        errors = fetch_errors(log_group, start_time)
        all_errors.extend(errors)
    if not all_errors:
        print('No errors found in the last 3 days.')
    else:
        print(f'Found {len(all_errors)} error events in the last 3 days:\n')
        for err in all_errors:
            print(f"[{err['timestamp']}] {err['log_group']} | {err['stream']}\n{err['message']}\n---")

if __name__ == '__main__':
    main()
