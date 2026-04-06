import unittest
from unittest.mock import patch, MagicMock
from models import ProductRecord
from content_generator import generate_poster_content
import json

class TestContentGenerator(unittest.TestCase):
    @patch("content_generator._build_client")
    def test_generate_poster_content_returns_scheme(self, mock_build_client):
        # Mocking OpenAI Client
        mock_client = MagicMock()
        mock_build_client.return_value = mock_client
        
        # Mock responses
        mock_response_phase1 = MagicMock()
        mock_response_phase1.choices = [
            MagicMock(message=MagicMock(content="```json\n{\"scheme_name\": \"test_scheme\", \"visual_style\": \"test_style\", \"headline\": \"test_headline\", \"subheadline\": \"test_sub\", \"body_copy\": [\"test1\", \"test2\"], \"cta\": \"test_cta\", \"scene_description\": \"test_scene\", \"layout_description\": \"test_layout\"}\n```"))
        ]
        
        mock_response_phase2 = MagicMock()
        mock_response_phase2.choices = [
            MagicMock(message=MagicMock(content="```\n8k resolution, masterpiece\n```"))
        ]
        
        # Sequentially return responses for the two API calls
        mock_client.chat.completions.create.side_effect = [mock_response_phase1, mock_response_phase2]
        
        record = ProductRecord(
            record_id="123",
            product_name="婴儿洗发水",
            benefits="温和无泪",
            visual_style="清新自然",
            brand_colors="#AABBCC"
        )
        
        scheme = generate_poster_content(record)
        
        self.assertEqual(scheme.scheme_name, "test_scheme")
        self.assertEqual(scheme.headline, "test_headline")
        self.assertEqual(scheme.image_prompt, "8k resolution, masterpiece")

    @patch("content_generator._build_client")
    def test_generate_poster_content_invalid_json_raises(self, mock_build_client):
        # Mocking OpenAI Client
        mock_client = MagicMock()
        mock_build_client.return_value = mock_client
        
        # Return invalid JSON
        mock_response_phase1 = MagicMock()
        mock_response_phase1.choices = [
            MagicMock(message=MagicMock(content="```json\n{invalid_json}\n```"))
        ]
        
        mock_client.chat.completions.create.return_value = mock_response_phase1
        
        record = ProductRecord(
            record_id="123",
            product_name="婴儿洗发水",
        )
        
        # Should raise ValueError ultimately
        with self.assertRaises(ValueError):
            # Because of retry, it will attempt 3 times and then reraise the original error
            generate_poster_content(record)

if __name__ == '__main__':
    unittest.main()
