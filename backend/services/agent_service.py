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
        self.client = Client(
            timeout=float(os.getenv('OLLAMA_TIMEOUT_SECONDS', '120'))
        )
        # Use the compatible text model for email analysis and mailbox questions.
        self.model_id = os.getenv('OLLAMA_TEXT_MODEL', 'llama3.2')
        self.vision_model_id = os.getenv('OLLAMA_VISION_MODEL', 'llama3.2-vision')
        self.num_predict = int(os.getenv('OLLAMA_NUM_PREDICT', '256'))

    async def analyze_email(
        self,
        email_content: str,
        attachments: List[dict] = None,
        focus: Optional[str] = None,
    ) -> EventExtraction:
        focus_instruction = (
            f"Only consider events relevant to this user focus: {focus}"
            if focus else ""
        )
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

        {focus_instruction}
        
        Ensure you ONLY return valid JSON.
        """
        
        try:
            response = self.client.generate(
                model=self.model_id,
                prompt=prompt,
                format='json',
                options={'num_predict': self.num_predict}
            )
            data = self._complete_event_data(self._parse_json_response(response['response']))
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

    async def analyze_with_pdf(
        self,
        email_content: str,
        pdf_bytes: bytes,
        focus: Optional[str] = None,
    ) -> EventExtraction:
        try:
            pdf_text = self._extract_pdf_text(pdf_bytes)
            if pdf_text.strip():
                return await self.analyze_email(
                    f"{email_content}\n\nPDF attachment text:\n{pdf_text[:12000]}",
                    focus=focus,
                )

            # Scanned PDFs need vision, but low resolution and two pages are enough
            # for the common case while keeping memory and inference time bounded.
            images = convert_from_bytes(pdf_bytes, dpi=100, first_page=1, last_page=2)
            image_parts = []

            for img in images:
                img.thumbnail((1400, 1400))
                buf = io.BytesIO()
                img.save(buf, format='JPEG', quality=70, optimize=True)
                image_parts.append(buf.getvalue())
            
            prompt = """
            Analyze this email and the attached PDF document images.
            Extract any important deadlines or events.
            
            Return a JSON object as specified:
            - is_event, title, start_time, end_time, location, description, sentiment, importance_score, reasoning, is_academic.
            """
            
            response = self.client.generate(
                model=self.vision_model_id,
                prompt=f"Email: {email_content}\n\nTask: {prompt}",
                images=image_parts,
                format='json',
                options={'num_predict': self.num_predict}
            )
            data = self._complete_event_data(self._parse_json_response(response['response']))
            return EventExtraction(**data)
        except Exception as e:
            print(f"Local PDF Analysis failed: {e}. Falling back to text-only analysis.")
            return await self.analyze_email(email_content, focus=focus)

    def _extract_pdf_text(self, pdf_bytes: bytes) -> str:
        """Read text PDFs without rendering pages into images."""
        try:
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(pdf_bytes))
            return "\n".join((page.extract_text() or "") for page in reader.pages[:10])
        except Exception:
            return ""

    async def answer_mail_question(self, question: str, emails: List[dict]) -> str:
        context = "\n\n".join(
            f"Subject: {email.get('subject', '(no subject)')}\n"
            f"From: {email.get('sender', '(unknown)')}\n"
            f"Date: {email.get('date', '(unknown)')}\n"
            f"Body: {email.get('body', '')[:5000]}"
            for email in emails
        )
        prompt = f"""
Answer the user's question using only the matching Gmail messages below.
Include concrete dates, subject names, senders, and relevant details when available.
If the messages do not contain the answer, say that clearly. Do not invent facts.

User question: {question}

Matching messages:
{context}
"""
        response = self.client.generate(
            model=self.model_id,
            prompt=prompt,
            options={'num_predict': self.num_predict},
        )
        return response['response'].strip()

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

    def _complete_event_data(self, data: dict) -> dict:
        """Fill missing model fields so incomplete JSON remains a safe result."""
        defaults = {
            'is_event': False,
            'title': None,
            'start_time': None,
            'end_time': None,
            'location': None,
            'description': None,
            'sentiment': 'Unknown',
            'importance_score': 0,
            'reasoning': 'The model did not identify a complete event.',
            'is_academic': False,
        }
        return {**defaults, **data}
