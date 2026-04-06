import unittest
from unittest.mock import patch, MagicMock
from models import QCResult
from qc_checker import perform_multimodal_qc
import json

class TestQCChecker(unittest.TestCase):
    
    @patch("qc_checker._build_client")
    def test_qc_passes(self, mock_build_client):
        # Mocking OpenAI Client
        mock_client = MagicMock()
        mock_build_client.return_value = mock_client
        
        # Mock response returning success JSON
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content="```json\n{\"passed\": true, \"issues\": [], \"confidence\": 0.95}\n```"))
        ]
        mock_client.chat.completions.create.return_value = mock_response
        
        result = perform_multimodal_qc("dummy_base64_poster", "dummy_base64_product")
        
        self.assertTrue(result.passed)
        self.assertEqual(len(result.issues), 0)
        self.assertGreater(result.confidence, 0.9)
        
    @patch("qc_checker._build_client")
    def test_qc_fails_with_issues(self, mock_build_client):
        # Mocking OpenAI Client
        mock_client = MagicMock()
        mock_build_client.return_value = mock_client
        
        # Mock response returning failure JSON
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content="```json\n{\"passed\": false, \"issues\": [\"Product is deformed\", \"Brand logo obscured\"], \"confidence\": 0.88}\n```"))
        ]
        mock_client.chat.completions.create.return_value = mock_response
        
        result = perform_multimodal_qc("dummy_base64_poster", "dummy_base64_product")
        
        self.assertFalse(result.passed)
        self.assertEqual(len(result.issues), 2)
        self.assertIn("Product is deformed", result.issues)
        
    @patch("qc_checker._build_client")
    def test_qc_handles_invalid_json(self, mock_build_client):
        # Mocking OpenAI Client
        mock_client = MagicMock()
        mock_build_client.return_value = mock_client
        
        # Mock response returning completely invalid output
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content="This is not json at all. I am an AI that refuses to output JSON."))
        ]
        mock_client.chat.completions.create.return_value = mock_response
        
        result = perform_multimodal_qc("dummy_base64_poster", "dummy_base64_product")
        
        # As per requirements, if it fails, default passed=True to avoid blocking pipeline
        self.assertTrue(result.passed)
        self.assertGreater(len(result.issues), 0)
        self.assertEqual(result.confidence, 0.0)

if __name__ == '__main__':
    unittest.main()
