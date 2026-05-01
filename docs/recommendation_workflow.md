# Recommendation Workflow

1. Collect public evidence from SEC filings, web sources, and Twitter.
2. Normalize and summarize the evidence into ticker-level notes.
3. Produce a Markdown report with thesis, reasons, sources, and risk notes.
4. Use the report for research review only.

## Environment Variables

- `GOOGLE_API_KEY`: Google model API key used by downstream summarization steps if enabled.
- `SEC_USER_AGENT`: User agent string required for SEC requests.
