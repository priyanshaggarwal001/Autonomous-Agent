import os
import json
import base64
import io
from ollama import Client
from typing import Optional, List
from pdf2image import convert_from_bytes
from PIL import Image
from ..models.event import EventExtraction

class AgentService:
    def __init__(self):
        # We don't need an API key for local Ollama, but we'll keep the client init
        self.client = Client()
        # Using llama3.2-vision for both text and image tasks
        self.model_id = 'llama3.2-vision'

    async def analyze_email(self, email_content: str, attachments: List[dict] = None) -> EventExtraction:
        prompt = f"""
        Analyze the following email content and any attached descriptions. 
        Your goal is to identify if there is an important event, deadline, or meeting mentioned.
        
        Return a JSON object with the following fields:
        - is_event (boolean): true if a specific date/time event or deadline is mentioned.
        - title (string): A concise title for the calendar event.
        - start_time (string): ISO 8601 format start time. If only a date is mentioned, use 09:00:00.
        - end_time (string): ISO 8601 format end time. If not specified, use 1 hour after start_time.
        - location (string): Where the event is happening.
        - description (string): A brief summary of the event.
        - sentiment (string): The emotion or tone of the email (e.g., Urgent, Formal, Casual, Marketing).
        - importance_score (integer): 0-10, where 10 is critically important (like a college deadline or client meeting).
        - reasoning (string): Why did you give it this importance score?
        - is_academic (boolean): true if it relates to college, university, or academic deadlines.

        Email Content:
        {email_content}
        
        Ensure you ONLY return valid JSON.
        """
        
        try:
            response = self.client.generate(
                model=self.model_id,
                prompt=prompt,
                format='json'
            )
            data = self._parse_json_response(response['response'])
            return EventExtraction(**data)
        except Exception as e:
            print(f"Error calling Ollama: {e}")
            # Fallback
            return EventExtraction(
                is_event=False, 
                sentiment="Unknown", 
                importance_score=0, 
                reasoning=f"Failed to process with local LLM: {str(e)}", 
                is_academic=False
            )

    async def analyze_with_pdf(self, email_content: str, pdf_bytes: bytes) -> EventExtraction:
        # Convert PDF pages to images for the local vision model
        try:
            images = convert_from_bytes(pdf_bytes)
            image_parts = []
            
            # For simplicity and performance, we'll process the first 3 pages if it's long
            for img in images[:3]:
                buf = io.BytesIO()
                img.save(buf, format='JPEG')
                image_parts.append(buf.getvalue())
            
            prompt = """
            Analyze this email and the attached PDF document images.
            Extract any important deadlines or events.
            
            Return a JSON object as specified:
            - is_event, title, start_time, end_time, location, description, sentiment, importance_score, reasoning, is_academic.
            """
            
            response = self.client.generate(
                model=self.model_id,
                prompt=f"Email: {email_content}\n\nTask: {prompt}",
                images=image_parts,
                format='json'
            )
            data = self._parse_json_response(response['response'])
            return EventExtraction(**data)
        except Exception as e:
            print(f"Local PDF Analysis failed: {e}. Falling back to text-only analysis.")
            return await self.analyze_email(email_content)

    def _parse_json_response(self, text: str) -> dict:
        """Extracts and parses JSON from a string that may contain extra text."""
        text = text.strip()
        
        data = None
        # 1. Try direct parsing
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # 2. Try extracting from markdown blocks
            if "```json" in text:
                try:
                    content = text.split("```json")[1].split("```")[0].strip()
                    data = json.loads(content)
                except (IndexError, json.JSONDecodeError):
                    pass
            elif "```" in text:
                try:
                    content = text.split("```")[1].split("```")[0].strip()
                    data = json.loads(content)
                except (IndexError, json.JSONDecodeError):
                    pass
                    
            # 3. Last resort: find the first '{' and last '}'
            if data is None:
                start_idx = text.find('{')
                end_idx = text.rfind('}')
                
                if start_idx != -1 and end_idx != -1:
                    try:
                        content = text[start_idx:end_idx + 1]
                        data = json.loads(content)
                    except json.JSONDecodeError:
                        pass
        
        if data is None:
            raise ValueError(f"Could not find valid JSON in response: {text[:100]}...")
            
        # If the model returned a list of one item, extract the item
        if isinstance(data, list) and len(data) > 0:
            data = data[0]
            
        if not isinstance(data, dict):
            raise ValueError(f"Parsed JSON is not a dictionary: {type(data)}")
            
        return data
