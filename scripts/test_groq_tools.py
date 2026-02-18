"""Quick smoke test: Groq + llama-3.3-70b-versatile tool calling."""
import os, sys, time
sys.path.insert(0, "src")

from dotenv import load_dotenv
load_dotenv()

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool


@tool
def get_price(ticker: str) -> str:
    """Get the current stock price."""
    return f'{{"price": 42.50, "ticker": "{ticker}"}}'


llm = ChatOpenAI(
    model="llama-3.3-70b-versatile",
    openai_api_key=os.getenv("GROQ_API_KEY"),
    openai_api_base="https://api.groq.com/openai/v1",
    temperature=0.1,
    request_timeout=15,
).bind_tools([get_price])

start = time.time()
resp = llm.invoke([HumanMessage(content="What is the price of AAPL?")])
elapsed = time.time() - start

print(f"Response in {elapsed:.1f}s")
print(f"Tool calls: {resp.tool_calls}")
print(f"Content: {resp.content[:200]!r}")
