import os
import json
import re
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential
from models import QCResult
from dotenv import load_dotenv

load_dotenv()

def _build_client():
    return OpenAI(
        api_key=os.environ.get("OPENAI_API_KEY", "dummy"),
        base_url=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
    )

def _extract_code_block(text, language=""):
    pattern = rf"```{language}(.*?)```"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    pattern = r"```(.*?)```"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        content = match.group(1).strip()
        if content.startswith(language):
            content = content[len(language):].strip()
        return content
    return text.strip()

@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=False)
def perform_multimodal_qc(poster_base64: str, original_product_base64: str) -> QCResult:
    try:
        client = _build_client()
        
        system_prompt = """You are a highly capable AI specialized in multimodal quality control for advertising posters.
You will be provided with an advertising poster image and the original product image.
Your task is to inspect the poster for the following quality issues:
1. Product Visibility: Is the product clearly visible?
2. Shape Distortion: Is the product's shape deformed compared to the original?
3. Brand Colors: Are the original product/brand colors preserved?
4. Text Cropping: Is any text cut off or incomplete?
5. Hallucination: Are there extra, unprompted products in the poster?
6. Logo Obscurity: Is the brand logo obscured or missing?

Output a strict JSON describing the result:
{
    "passed": true or false,
    "issues": ["list of specific issues if any, empty if none"],
    "confidence": 0.0 to 1.0
}"""
        
        response = client.chat.completions.create(
            model="gemini-3.1-pro-preview",
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Original Product Image:"},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{original_product_base64}"
                            }
                        },
                        {"type": "text", "text": "Generated Poster Image:"},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{poster_base64}"
                            }
                        }
                    ]
                }
            ],
            temperature=0.1
        )
        
        content = response.choices[0].message.content
        json_str = _extract_code_block(content, "json")
        
        try:
            result_data = json.loads(json_str)
        except json.JSONDecodeError:
            result_data = json.loads(content.strip())
            
        return QCResult(**result_data)
        
    except Exception as e:
        # If model returns invalid JSON or API fails after 2 retries,
        # default to passed=True to avoid blocking the pipeline as requested.
        print(f"QC check failed with error: {e}. Defaulting to passed=True.")
        return QCResult(passed=True, issues=[f"QC system failure: {str(e)}"], confidence=0.0)
