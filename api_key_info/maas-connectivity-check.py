from langchain_openai import ChatOpenAI
import os
import httpx
client = httpx.Client(verify=False)
llm = ChatOpenAI(
   base_url="https://genailab.tcs.in", # set openai_api_base to the LiteLLMProxy
   model = "azure/genailab-maas-gpt-4o-mini",
   api_key="sk-FHCqt-_flSjGm2TRjj1wXw",
   http_client = client
)

print(llm.invoke("Hi"))