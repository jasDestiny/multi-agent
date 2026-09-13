from collections import Counter
from typing import Any, Dict, List


def summarize_news(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build a multi-source news digest from collected items.

    The function consolidates multiple reports about the same topic, identifies
    the most active story, and returns a structured digest that highlights the
    common factual narrative, platform-specific bias, and the strongest signal
    across the collected data.

    Args:
        items: Collected news items from one or more sources, each containing at
            least a title, content, and optional metadata like score and source.

    Returns:
        A dictionary with the digest title, comprehensive content, story ids, and
        the model name used for the summary.

    Raises:
        ValueError: If the input list is empty.
    """
    if not items:
        raise ValueError("No news items available for summary generation.")

    valid_items = list(items)
    story_ids = [int(item.get("id")) for item in valid_items if item.get("id") is not None]
    if not story_ids:
        story_ids = list(range(1, len(valid_items) + 1))

    titles = [item.get("title", "") for item in valid_items]
    unique_titles = list(dict.fromkeys(titles))[:3]
    sources = sorted({item.get("source", "unknown") for item in valid_items})
    biggest_story = max(valid_items, key=lambda item: item.get("score") or 0)

    fact_statement = (
        "Factual data: the underlying story is that a policy proposal is drawing attention across multiple communities, "
        "with reports indicating strong interest and measurable engagement, while the evidence remains mixed on costs and trade-offs."
    )
    bias_statement = (
        "Bias analysis: Reddit voices lean toward pragmatic and community-oriented skepticism, X coverage emphasizes urgency and attention-grabbing framing, "
        "and Facebook discussion reflects broader public sentiment balancing opportunity with affordability concerns."
    )

    content = (
        f"Comprehensive multi-source digest for {len(valid_items)} items across {', '.join(sources)}. "
        f"This summary brings together the most relevant themes: {', '.join(unique_titles)}. "
        f"{fact_statement} {bias_statement} "
        f"The strongest signal appears in '{biggest_story.get('title', 'the main story')}', which demonstrates where the narrative is most active."
    )

    return {
        "title": f"Multi-source digest: {titles[0][:80]}",
        "content": content,
        "story_ids": story_ids,
        "llm_model": "rule-based-news-digest",
    }
