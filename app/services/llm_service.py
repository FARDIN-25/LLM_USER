"""
LLM service - Language detection and prompt creation.
"""
import re
import logging

logger = logging.getLogger("fintax")


def detect_language(text):
    """Detect if text contains Tamil or other Indian languages"""
    if not text:
        return "english"
    
    # Check for Tamil script (Tamil Unicode range: 0B80-0BFF)
    tamil_pattern = re.compile(r'[\u0B80-\u0BFF]+')
    if tamil_pattern.search(text):
        return "tamil"
    
    # Check for other Indian language scripts if needed
    # Hindi: \u0900-\u097F, Telugu: \u0C00-\u0C7F, etc.
    
    return "english"


def create_prompt(context, question, preferred_language: str = None):
    """Create a comprehensive prompt for the LLM with language detection.

    If `preferred_language` is provided (e.g. 'english' or 'tamil'), it will be
    used to influence the language instructions. Otherwise language is detected
    from the question text as before.
    """
    context = context or "No specific context available."
    question = question or "No question provided."
    
    # Determine language preference: explicit preferred_language overrides detection
    if preferred_language:
        question_lang = preferred_language.lower()
    else:
        # Detect language of the question
        question_lang = detect_language(question)
        # Default to English even if Tamil is detected, unless explicitly requested.
        # This makes English the default response language for backward compatibility.
        if question_lang == "tamil":
            question_lang = "english"
    
    # Language-specific instructions
    if question_lang == "tamil":
        language_instruction = """CRITICAL LANGUAGE REQUIREMENT: The user's question is in Tamil language (தமிழ்). 

YOU MUST:
1. Respond COMPLETELY in Tamil language (தமிழில்)
2. Write your ENTIRE answer using Tamil script
3. Do NOT use English - use ONLY Tamil
4. Provide detailed, comprehensive answers in Tamil
5. Use proper Tamil grammar and vocabulary
6. If technical terms are needed, use Tamil translations with English in parentheses

EXAMPLE OF CORRECT FORMAT:
Question: GST பதிவு வரம்பு என்ன?
Answer: GST பதிவு வரம்பு பற்றிய விவரங்கள்: [தமிழில் முழு பதில்]

START YOUR ANSWER NOW IN TAMIL:"""
    else:
        # Default: respond in English unless Tamil was explicitly requested via preferred_language
        language_instruction = "Respond COMPLETELY in English. If the user explicitly requested Tamil via the 'language' parameter, respond in Tamil instead."

    # Check if context is empty or just placeholder
    has_context = context and context.strip() and context != "No specific context available."
    
    context_instruction = ""
    if not has_context:
        context_instruction = """
IMPORTANT: No specific context was found in the knowledge base for this question. 
You MUST still provide a helpful answer using your general knowledge of Indian taxation, GST, and financial regulations.
Do NOT say you cannot answer - provide the best answer you can based on your knowledge.
"""
    else:
        context_instruction = """
IMPORTANT: If the context above is not directly relevant to the user's question, use your general tax knowledge to answer.
You MUST always provide a response. Never say you cannot answer.
"""

    # Build context section with emphasis
    if has_context:
        context_section = f"""CONTEXT FROM KNOWLEDGE BASE (USE THIS INFORMATION TO ANSWER THE QUESTION):
{context}

IMPORTANT: The context above contains relevant information from the knowledge base. You MUST prioritize and use this information when answering the question. If the context directly answers the question, use it. If the context provides partial information, combine it with your general knowledge to give a complete answer."""
    else:
        context_section = """CONTEXT FROM KNOWLEDGE BASE:
No specific context found in the knowledge base for this question.

IMPORTANT: Since no specific context was found, use your general knowledge of Indian taxation, GST, and financial regulations to provide a comprehensive answer."""
    
    prompt = f"""You are a professional tax assistant specializing in Indian taxation, GST, and financial regulations.

{language_instruction}
{context_instruction}

{context_section}

USER QUESTION:
{question}

INSTRUCTIONS (FOLLOW THESE CAREFULLY):
1. **PRIORITIZE CONTEXT**: If context from the knowledge base is provided above, you MUST use it as the primary source for your answer. Reference specific details from the context.
2. **COMBINE KNOWLEDGE**: If the context provides partial information, combine it with your general tax knowledge to give a complete, comprehensive answer.
3. **BE SPECIFIC**: Provide specific, practical, and actionable advice. Include relevant numbers, percentages, dates, and procedures when available.
4. **FORMAT STRUCTURE**: You can use structured format with:
   - Start with an introductory paragraph explaining the topic
   - Use numbered sections (1., 2., 3.) for main categories/topics - make these BOLD titles like **1. Topic Name:**
   - Under each numbered section, use bullet points (-, •, or ●) for sub-items
   - Use **bold** formatting for important terms, key concepts, and section titles
4a. **NO MARKDOWN HEADER SYMBOLS**: Do NOT use Markdown header syntax (any lines starting with `#`, e.g., `#`, `##`, `###`). Use bold (`**Title**`) or plain text lines for section titles instead.
5. **HIGHLIGHT IMPORTANT WORDS**: Use **bold** markdown formatting (**text**) for:
   - Section titles (like **1. Types of GST:**)
   - Important terms and concepts
   - Key definitions
   - Critical information
6. **SHOW CALCULATIONS**: If discussing calculations or formulas, show the methodology step-by-step.
7. **CRITICAL - ALWAYS RESPOND**: You MUST always provide a response. Never say you cannot answer or that you don't have information.
8. **CRITICAL - LANGUAGE**: Respond COMPLETELY in English by default. If the user explicitly provided a different `language` (for example, 'tamil'), follow that preference and respond in that language.
9. **MINIMUM LENGTH**: Your response must be at least 50 words and provide substantial, detailed information.

Now provide your detailed answer in the same language as the question:
"""
    return prompt

