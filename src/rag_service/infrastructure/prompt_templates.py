"""
prompt_templates.py

Refactored prompt template system:
- Simplified to 2 production-ready templates: 'rag' and 'computation'.
- Production-grade routing logic.
- Cleaned legacy guardrails and formatting rules.
"""

from typing import List, Dict, Any, Optional, Tuple
import re
from fastapi import FastAPI, HTTPException, Query, Body
from pydantic import BaseModel
import json
import os
import time
import logging

logger_prompt = logging.getLogger("fintax")

# --------------------------------------------------------------------
# 🔹 Helper Functions
# --------------------------------------------------------------------

def bullet_list(items: List[str], symbol: str = "-") -> str:
    """Return bullet-style formatted list using plain text bullets."""
    return "\n".join([f"{symbol} {item}" for item in items])


def numbered_list(items: List[str], symbol: str = "") -> str:
    """Return a simple numbered list in plain text."""
    return "\n".join([f"{i+1}. {item}" for i, item in enumerate(items)])


# --------------------------------------------------------------------
# 🔹 Pydantic Models for FastAPI
# --------------------------------------------------------------------

class PromptRequest(BaseModel):
    """Model for prompt generation requests."""
    template_id: str
    parameters: Dict[str, Any] = {}

class BuildPromptRequest(BaseModel):
    """Model for build_prompt requests."""
    template_name: str = "general"
    context: str = ""
    question: str = ""
    examples_count: int = 1
    require_chain_of_thought: bool = False
    use_query_expansion: bool = False

class TemplateInfo(BaseModel):
    """Model for template information."""
    id: str
    category: str
    title: str
    description: str
    required_fields: List[str]
    example_input: Dict[str, Any]

# --------------------------------------------------------------------
# 🔹 Prompt Library (Simplified to 2 templates)
# --------------------------------------------------------------------

PROMPT_LIBRARY = [
    {
        "id": "rag",
        "category": "Retrieval (RAG)",
        "title": "Professional RAG Answer Format",
        "description": "Default structured format for all tax and GST queries",
        "required_fields": ["user_query", "retrieved_context", "chat_history"],
        "template": (
            "You are a professional AI assistant and Indian tax expert.\n\n"
            "CURRENT INTENT: {intent}\n\n"
            "CONTEXT:\n{retrieved_context}\n\n"
            "CONVERSATION HISTORY:\n{chat_history}\n\n"
            "{user_profile}"
            "USER QUESTION:\n{user_query}\n\n"
            "INSTRUCTIONS:\n\n"
            "* The USER PROFILE is the absolute source of truth for all personal details about the USER (Name, PAN, Tax Regime, Financials). If the CONTEXT or history contains different names or details, IGNORE them for personal questions.\n"
            "* Greet the user by their Name if it is provided in the USER PROFILE section below.\n"
            "* Understand the user's intent clearly\n"
            "* LANGUAGE RULE: Always respond in the SAME language as the USER QUESTION. If the user question is in English, the answer MUST be in English, even if the history or greetings were in another language.\n"
            "* Use CONTEXT as the primary source\n"
            "* If context is insufficient, use general knowledge carefully\n"
            "* Do NOT hallucinate unknown facts\n"
            "* Do NOT repeat previous answers\n"
            "* Keep the response concise and relevant (max 6–8 points)\n\n"
            "OUTPUT FORMAT:\n\n"
            "* Start with a **BOLD HEADING** representing the core answer\n"
            "* Use bullet points for all detailed points\n"
            "* Ensure each bullet point is clear and standalone\n"
            "* Add an example only if it helps clarify a complex rule\n\n"
            "## FINAL ANSWER:"
        ),
        "default_params": {
            "retrieved_context": "Context not available. Answer using general knowledge.",
            "chat_history": "",
            "user_profile": ""
        },
        "example_input": {
            "user_query": "What is the GST rate for restaurant services?",
            "retrieved_context": "GST for restaurant services is 5% without ITC.",
            "chat_history": "No history."
        }
    },
    {
        "id": "computation",
        "category": "Computation",
        "title": "Tax or GST Calculation",
        "description": "Step-by-step breakdown for numerical tax queries",
        "required_fields": ["user_query", "financial_data"],
        "template": (
            "You are a professional AI assistant and Indian tax expert specializing in calculations.\n\n"
            "USER QUESTION:\n{user_query}\n\n"
            "FINANCIAL DATA:\n{financial_data}\n\n"
            "INSTRUCTIONS:\n\n"
            "* Start with a **BOLD SUMMARY** of the result\n"
            "* Use bullet points to show the step-by-step breakdown of the calculation\n"
            "* Include the final result clearly highlighted at the end\n"
            "* Provide ONLY the calculation and direct result; no unnecessary explanation\n\n"
            "## CALCULATION BREAKDOWN:"
        ),
        "default_params": {
            "financial_data": ""
        },
        "example_input": {
            "user_query": "Calculate GST on 10000 @ 18%",
            "financial_data": "Principal: 10000; Rate: 18%"
        }
    },
    {
        "id": "greeting",
        "category": "Small Talk",
        "title": "Personalized Greeting",
        "description": "Friendly welcome using user profile data",
        "required_fields": ["user_query", "user_profile"],
        "template": (
            "You are a friendly and helpful AI assistant for the Bhaaskar platform.\n\n"
            "{user_profile}\n"
            "USER QUESTION: {user_query}\n\n"
            "INSTRUCTIONS:\n"
            "* Respond with a simple, friendly confirmation based ONLY on the USER PROFILE.\n"
            "* If the user corrected their name or PAN, acknowledge the update directly (e.g., 'Got it, Manohar! I've updated your name.').\n"
            "* CRITICAL: Do NOT bring in legal procedures, forms, tax advice, or ANY technical GST/Tax information for these turns. If the user asks for their name, JUST give their name.\n\n"
            "## RESPONSE:"
        ),
        "default_params": {
            "user_profile": ""
        },
        "example_input": {
            "user_query": "Hello",
            "user_profile": "- Name: Madhan"
        }
    }
]

# --------------------------------------------------------------------
# 🔹 Template Routing & Logic
# --------------------------------------------------------------------

RAG_APPLICABLE_TEMPLATE_IDS = ["rag", "computation"]

def detect_template_from_question(question: str) -> Tuple[str, Dict[str, Any]]:
    """Detect if the query requires a calculation or the default RAG template."""
    if not question:
        return "rag", {}
    
    q = question.lower()
    # Simple logic for numerical/calculation intent: Keywords + Numbers
    if any(char.isdigit() for char in q) and any(k in q for k in ["gst", "tax", "amount", "calculate", "compute", "rate", "percentage", "%"]):
        return "computation", {"financial_data": question}
            
    return "rag", {}

def get_prompt(template_id: str, **kwargs) -> str:
    """Fetch and format the selected prompt template."""
    # Pre-process rich metadata into user_profile string if present
    metadata = kwargs.get("metadata", {})
    user_profile_text = ""
    if metadata:
        profile = metadata.get("profile", {})
        financials = metadata.get("financials", {})
        memory = metadata.get("interaction_memory", {})
        notices = metadata.get("notices", {})
        
        lines = []
        if profile.get("name"): lines.append(f"- Name: {profile.get('name')}")
        if profile.get("pan"): lines.append(f"- PAN: {profile.get('pan')}")
        if profile.get("tan"): lines.append(f"- TAN: {profile.get('tan')}")
        if financials.get("tax_regime"): lines.append(f"- Tax Regime: {financials.get('tax_regime')}")
        if financials.get("income_sources"): lines.append(f"- Income Sources: {', '.join(financials.get('income_sources'))}")
        
        active_notices = notices.get("active_notices", [])
        if active_notices and isinstance(active_notices, list):
            lines.append(f"- Active Notices: {len(active_notices)} pending")
            
        if memory.get("last_topic"): lines.append(f"- Last Topic: {memory.get('last_topic')}")
        
        if lines:
            user_profile_text = "USER PROFILE:\n" + "\n".join(lines) + "\n\n"
            logger_prompt.info(f"[PROMPT DEBUG] Added USER PROFILE to prompt:\n{user_profile_text}")
            
    kwargs["user_profile"] = user_profile_text

    for tpl in PROMPT_LIBRARY:
        if tpl["id"] == template_id:
            params = tpl.get("default_params", {}).copy()
            params.update(kwargs)
            try:
                return tpl["template"].format(**params)
            except KeyError as e:
                logger_prompt.error(f"Missing required field {e} for template {template_id}")
                return tpl["template"]
    
    # Fallback to 'rag' if template_id is invalid
    if template_id != "rag":
        return get_prompt("rag", **kwargs)
    
    return "Error: Template not found."

def build_prompt_from_template(template_id: str, params: Dict[str, Any]) -> str:
    """Connector for pipeline integration."""
    return get_prompt(template_id, **params)

def get_template_info(template_id: str) -> Optional[Dict[str, Any]]:
    """Return metadata about a specific template."""
    for tpl in PROMPT_LIBRARY:
        if tpl["id"] == template_id:
            return tpl
    return None

def build_prompt(template_name: str = "general",
                 context: str = "",
                 question: str = "",
                 **kwargs) -> str:
    """Simplified dynamic prompt builder for legacy support."""
    template_id = "computation" if template_name == "calculation" else "rag"
    params = {
        "user_query": question,
        "retrieved_context": context,
        "financial_data": question if template_id == "computation" else ""
    }
    params.update(kwargs)
    return get_prompt(template_id, **params)

# --------------------------------------------------------------------
# 🔹 FastAPI Application
# --------------------------------------------------------------------

app = FastAPI(
    title="Tax & Accounting Prompt Templates API",
    description="Professional Prompt Template Library for Tax, GST, and Accounting Chatbots",
    version="1.0.0"
)

@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "Tax & Accounting Prompt Templates API",
        "version": "1.0.0",
        "endpoints": {
            "/templates": "Get all available templates",
            "/templates/{template_id}": "Get specific template information",
            "/generate": "Generate a prompt from template",
            "/build": "Build a dynamic prompt",
            "/categories": "Get all template categories",
            "/health": "Health check endpoint"
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": str(time.time())}

@app.get("/templates")
async def get_all_templates():
    """Get all available templates."""
    templates = []
    for tpl in PROMPT_LIBRARY:
        templates.append({
            "id": tpl["id"],
            "category": tpl["category"],
            "title": tpl["title"],
            "description": tpl["description"],
            "required_fields": tpl["required_fields"]
        })
    return {"templates": templates, "count": len(templates)}

@app.get("/templates/{template_id}")
async def get_template(template_id: str):
    """Get specific template information."""
    template_info = get_template_info(template_id)
    if template_info:
        return template_info
    raise HTTPException(status_code=404, detail=f"Template '{template_id}' not found")

@app.post("/generate")
async def generate_prompt(request: PromptRequest):
    """Generate a prompt from a template."""
    prompt = get_prompt(request.template_id, **request.parameters)
    return {
        "template_id": request.template_id,
        "prompt": prompt,
        "parameters": request.parameters
    }

@app.post("/build")
async def build_dynamic_prompt(request: BuildPromptRequest):
    """Build a dynamic prompt."""
    prompt = build_prompt(
        template_name=request.template_name,
        context=request.context,
        question=request.question,
        **request.dict()
    )
    return {
        "template_name": request.template_name,
        "prompt": prompt,
        "parameters": request.dict()
    }

@app.get("/categories")
async def get_categories():
    """Get all template categories."""
    categories = {}
    for tpl in PROMPT_LIBRARY:
        cat = tpl["category"]
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(tpl["id"])
    
    return {
        "categories": categories,
        "total_categories": len(categories)
    }

@app.get("/generate/{template_id}")
async def generate_prompt_get(
    template_id: str,
    params: Optional[str] = Query(None, description="JSON string of parameters")
):
    """Generate prompt using GET request (for simple use cases)."""
    parameters = {}
    if params:
        try:
            parameters = json.loads(params)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON parameters")
    
    prompt = get_prompt(template_id, **parameters)
    return {
        "template_id": template_id,
        "prompt": prompt,
        "parameters": parameters
    }
