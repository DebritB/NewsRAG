import sys
sys.path.append('d:/NewsRAG')
import json
import chatbot_lambda

# Patch run functions to avoid external API calls
chatbot_lambda.run_direct_bedrock = lambda prompt, **kwargs: 'Dummy bedrock response.'
chatbot_lambda.run_langchain_llm = lambda query, context_text, **kwargs: 'Dummy langchain response.'
chatbot_lambda.generate_embedding = lambda text: [0.01, 0.02, 0.03]
chatbot_lambda.LANGCHAIN_AVAILABLE = False

# Fake MongoDB Client + collection to avoid network dependence
class FakeCollection:
	def aggregate(self, pipeline):
		return [{'title':'Stock rally', 'summary':'A big rally in the markets today driven by tech stocks','score':0.92,'source':'Example News','published_at':'2025-12-12','url':'https://example.com/article'}]

class FakeClient:
	def __init__(self, uri):
		pass
	def __getitem__(self, name):
		return {'articles': FakeCollection()}
	def close(self):
		pass

chatbot_lambda.MongoClient = FakeClient

event = {'body': json.dumps({'query': 'What happened in markets today?', 'max_results': 5})}
response = chatbot_lambda.lambda_handler(event, None)
print('StatusCode:', response['statusCode'])
print('Body:', response['body'])
