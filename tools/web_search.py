from tavily import TavilyClient

from config import TAVILY_API_KEY

client = TavilyClient(api_key=TAVILY_API_KEY)


def search(query, max_results=5):
    return client.search(
        query=query,
        max_results=max_results,
    )