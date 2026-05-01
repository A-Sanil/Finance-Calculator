from quant_agent.recommendations import RecommendationEngine


def test_recommendation_report_markdown_contains_sections() -> None:
    engine = RecommendationEngine()
    report = engine.build_report(["AAPL"])
    markdown = report.to_markdown()

    assert "# Stock Recommendation Digest" in markdown
    assert "## AAPL" in markdown
    assert "Sources:" in markdown
    assert "Risk notes:" in markdown or "Notes" in markdown
