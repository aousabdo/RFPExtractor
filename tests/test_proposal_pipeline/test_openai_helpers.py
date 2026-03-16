"""Tests for OpenAI helper functions."""

import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from proposal_pipeline.models import RFPAnalysis
from proposal_pipeline.openai_helpers import (
    chat_completion,
    get_client,
    save_structured_output,
    structured_output,
)


class TestGetClient:
    @patch("proposal_pipeline.openai_helpers.OpenAI")
    def test_with_api_key(self, mock_openai):
        get_client("sk-test-key")
        mock_openai.assert_called_once_with(api_key="sk-test-key")

    @patch("proposal_pipeline.openai_helpers.OpenAI")
    def test_without_api_key(self, mock_openai):
        get_client()
        mock_openai.assert_called_once_with()


class TestChatCompletion:
    def test_returns_content(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Hello, world!"
        mock_client.chat.completions.create.return_value = mock_response

        result = chat_completion(
            client=mock_client,
            system_prompt="You are helpful.",
            user_prompt="Say hello.",
        )

        assert result == "Hello, world!"
        mock_client.chat.completions.create.assert_called_once()

    def test_passes_parameters(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "OK"
        mock_client.chat.completions.create.return_value = mock_response

        chat_completion(
            client=mock_client,
            system_prompt="system",
            user_prompt="user",
            model="gpt-5",
            temperature=0.5,
            max_tokens=2048,
        )

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["model"] == "gpt-5"
        # gpt-5 is a reasoning model — temperature is skipped, max_completion_tokens used
        assert "temperature" not in call_kwargs
        assert call_kwargs["max_completion_tokens"] == 2048


class TestStructuredOutput:
    def test_valid_response(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        valid_json = json.dumps({
            "customer": "DHS",
            "scope": "Modernize systems",
            "tasks": [],
            "requirements": [],
            "dates": [],
        })
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = valid_json
        mock_client.chat.completions.create.return_value = mock_response

        result = structured_output(
            client=mock_client,
            system_prompt="Extract RFP data.",
            user_prompt="Analyze this RFP.",
            response_model=RFPAnalysis,
        )

        assert isinstance(result, RFPAnalysis)
        assert result.customer == "DHS"

    def test_retry_on_invalid_json(self):
        mock_client = MagicMock()

        # First call returns invalid JSON, second returns valid
        invalid_response = MagicMock()
        invalid_response.choices = [MagicMock()]
        invalid_response.choices[0].message.content = "not json"

        valid_response = MagicMock()
        valid_json = json.dumps({
            "customer": "DOD",
            "scope": "Build portal",
            "tasks": [],
            "requirements": [],
            "dates": [],
        })
        valid_response.choices = [MagicMock()]
        valid_response.choices[0].message.content = valid_json

        mock_client.chat.completions.create.side_effect = [
            invalid_response,
            valid_response,
        ]

        result = structured_output(
            client=mock_client,
            system_prompt="Extract.",
            user_prompt="Analyze.",
            response_model=RFPAnalysis,
            max_retries=2,
        )

        assert result.customer == "DOD"
        assert mock_client.chat.completions.create.call_count == 2

    def test_raises_after_max_retries(self):
        mock_client = MagicMock()
        invalid_response = MagicMock()
        invalid_response.choices = [MagicMock()]
        invalid_response.choices[0].message.content = "not json"
        mock_client.chat.completions.create.return_value = invalid_response

        with pytest.raises(Exception):
            structured_output(
                client=mock_client,
                system_prompt="Extract.",
                user_prompt="Analyze.",
                response_model=RFPAnalysis,
                max_retries=1,
            )

        # 1 initial + 1 retry = 2 calls
        assert mock_client.chat.completions.create.call_count == 2


class TestSaveStructuredOutput:
    def test_saves_json_file(self):
        rfp = RFPAnalysis(customer="Test Agency", scope="Test scope")

        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                path = save_structured_output(rfp, "test_output.json")

                assert os.path.exists(path)
                with open(path) as f:
                    data = json.load(f)
                assert data["customer"] == "Test Agency"
            finally:
                os.chdir(original_cwd)
