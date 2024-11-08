import logging
from fastapi import FastAPI, UploadFile, File, Form, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request
from anthropic import Anthropic
import base64
import os
from sqlalchemy.orm import Session
from models import SessionLocal, Conversation, Message
from typing import Optional
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Dependency to get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    logger.info("Received request for root endpoint")
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/process")
async def process_pdf(
    request: Request,
    instruction: str = Form(...),
    file: Optional[UploadFile] = File(None),
    conversation_id: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    logger.info(f"\n=== Processing Request ===")
    logger.info(f"Conversation ID: {conversation_id}")
    logger.info(f"Has file: {file is not None}")
    logger.info(f"Instruction: {instruction}")

    try:
        # Handle conversation_id
        conv_id = None
        if conversation_id and conversation_id.strip():
            try:
                conv_id = int(conversation_id)
                logger.info(f"Parsed conversation_id: {conv_id}")
            except ValueError:
                logger.error(f"Invalid conversation_id format: {conversation_id}")
                return JSONResponse(
                    status_code=422,
                    content={"detail": "Invalid conversation ID format"}
                )
        
        # Get or create conversation
        if conv_id:
            conversation = db.query(Conversation).filter(Conversation.id == conv_id).first()
            if not conversation:
                logger.error(f"Conversation not found: {conv_id}")
                return JSONResponse(
                    status_code=404,
                    content={"detail": "Conversation not found"}
                )
        elif file:
            conversation = Conversation(pdf_name=file.filename)
            db.add(conversation)
            db.flush()
            logger.info(f"Created new conversation: {conversation.id}")
        else:
            logger.error("Neither valid conversation_id nor file provided")
            return JSONResponse(
                status_code=422,
                content={"detail": "Either file or valid conversation_id must be provided"}
            )

        # Read and encode PDF
        file_content = await file.read()
        pdf_data = base64.standard_b64encode(file_content).decode('utf-8')
        logger.info("PDF file read and encoded")

        # Get ALL previous messages for this conversation
        previous_messages = []
        if conversation:
            previous_messages = db.query(Message).filter(
                Message.conversation_id == conversation.id
            ).order_by(Message.created_at).all()

        # Create messages array for Claude
        messages = []
        
        # Add PDF document only on first message
        if file:
            messages.append({
                "role": "user",
                "content": [{
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": pdf_data
                    }
                }]
            })

        # Add conversation history
        for msg in previous_messages:
            messages.append({
                "role": msg.role,
                "content": [{"type": "text", "text": msg.content}]
            })

        # Add current instruction
        messages.append({
            "role": "user",
            "content": [{"type": "text", "text": instruction}]
        })

        # Save user message
        user_message = Message(
            conversation_id=conversation.id,
            role="user",
            content=instruction
        )
        db.add(user_message)
        db.flush()

        # Get Claude's response
        response = client.beta.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1024,
            betas=["pdfs-2024-09-25"],
            messages=messages
        )

        response_text = ''.join(
            block.text for block in response.content if block.type == 'text'
        )

        # Save assistant message
        assistant_message = Message(
            conversation_id=conversation.id,
            role="assistant",
            content=response_text
        )
        db.add(assistant_message)
        db.commit()

        return templates.TemplateResponse("response_partial.html", {
            "request": request,
            "instruction": instruction,  # Pass the instruction to template
            "response_text": response_text,
            "conversation_id": conversation.id
        })
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"detail": "An error occurred while processing your request"}
        )

@app.post("/test-upload")
async def test_upload(
    request: Request,
    instruction: str = Form(...),
    file: Optional[UploadFile] = File(None),
    conversation_id: Optional[int] = Form(None)
):
    logger.info("\n=== Test Upload Request ===")
    logger.info(f"Instruction: {instruction}")
    logger.info(f"File: {file.filename if file else None}")
    logger.info(f"Conversation ID: {conversation_id}")
    
    form_data = await request.form()
    logger.info("\nAll form data:")
    for key, value in form_data.items():
        if isinstance(value, UploadFile):
            logger.info(f"{key}: <UploadFile: {value.filename}>")
        else:
            logger.info(f"{key}: {value}")
    
    return JSONResponse(content={
        "message": "Test upload received",
        "instruction": instruction,
        "file_name": file.filename if file else None,
        "conversation_id": conversation_id
    })