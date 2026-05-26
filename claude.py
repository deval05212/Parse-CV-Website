import boto3
import json

client = boto3.client(
    service_name="bedrock-runtime",
    region_name="us-east-1"
)

body = {
    "anthropic_version": "bedrock-2023-05-31",
    "max_tokens": 300,
    "messages": [
        {
            "role": "user",
            "content": "Hello Claude"
        }
    ]
}

response = client.invoke_model(
    modelId="anthropic.claude-opus-4-7",
    body=json.dumps(body)
)

response_body = json.loads(response["body"].read())

print(response_body)