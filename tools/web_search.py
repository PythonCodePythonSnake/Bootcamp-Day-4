"""Web search tool — Tavily search API.

The TavilyClient is constructed lazily inside search() so that importing this
module never fails when TAVILY_API_KEY is absent.  The function also extracts
the "results" list from Tavily's response object, so callers receive a plain
list[dict] rather than a raw response envelope.
"""

from config import TAVILY_API_KEY


def search(query: str, max_results: int = 5) -> list[dict]:
    """Search the web using Tavily and return a list of result dicts.

    Each result dict typically contains: title, url, content, score.
    Returns an empty list if the API call fails or no results are found.
    """
    from tavily import TavilyClient

    client = TavilyClient(api_key=TAVILY_API_KEY)
    response = client.search(query=query, max_results=max_results)

    # Tavily returns {"results": [...], "query": ..., ...}
    return response.get("results", [])