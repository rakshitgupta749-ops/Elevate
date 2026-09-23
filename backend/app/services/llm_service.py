import os
import httpx
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
if os.path.exists(env_path):
    load_dotenv(env_path)
load_dotenv()

def get_llm():
    client = httpx.Client(verify=False)
    api_key = os.getenv("TCS_API_KEY", "sk-FHCqt-_flSjGm2TRjj1wXw")
    return ChatOpenAI(
        base_url="https://genailab.tcs.in",
        model="azure/genailab-maas-gpt-4o-mini",
        api_key=api_key,
        http_client=client,
        temperature=0.7
    )
