# AIGregate

[filipemd.github.io/aigregate](https://filipemd.github.io/aigregate)

MVP of a technology news aggregator using AI and the Gemini API.

It works by searching for news in RSS feeds from programming subreddits.

To run it, obtain a free Gemini API key, set it as the `GEMINI_API_KEY` environment variable, and run the `scripts/create_news_summary.py` (installing the PIP packages from `requirements.txt`) script, specifying a Markdown file as the output parameter.

Instead of using a server, it uses the Hugo SSG (Static Site Generator) to generate the HTML and GitHub Actions to generate the post every day at 11 PM.