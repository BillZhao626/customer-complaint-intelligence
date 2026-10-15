from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.chains.langchain_complaint_chain import analyze_email_with_langchain
from src.config.llm_config import get_llm_config


def main() -> None:
    config = get_llm_config()
    summary = config.safe_summary()

    print(f"LLM provider: {summary['provider']}")
    print(f"LLM model: {summary['model_name']}")
    print(f"LLM base URL: {summary['base_url']}")
    print(f"LLM API enabled: {summary['enabled']}")
    print(f"LLM API key configured: {summary['api_key_configured']}")

    if not config.enable_api:
        print("LLM_ENABLE_API is not true. Skipping real API connection test without error.")
        return

    errors = config.validation_errors()
    if errors:
        print("Configuration is not ready for API testing:")
        for error in errors:
            print(f"- {error}")
        return

    result = analyze_email_with_langchain(
        "connection-test-001",
        "I bought a laptop from Shanghai Pudong Store yesterday. It works well and I am happy with the service.",
    )
    print(f"Backend: {result.get('analyzer_backend')}")
    print(f"Model: {result.get('model_name')}")
    print(f"API attempted: {result.get('api_attempted')}")
    print(f"API retry count: {result.get('api_retry_count')}")
    print(f"Parse success: {result.get('parse_success')}")
    print(f"Schema validation success: {result.get('schema_validation_success')}")
    api_error_message = result.get("api_error_message") or result.get("error_message")
    if api_error_message:
        print(f"API error message: {api_error_message}")
        raw_response_preview = result.get("raw_response_preview")
        if raw_response_preview:
            print(f"Raw response preview: {raw_response_preview}")
    print(f"Sentiment: {result.get('sentiment')}")
    print(f"Summary: {result.get('summary')}")


if __name__ == "__main__":
    main()
