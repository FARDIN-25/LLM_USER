class IntentClassifier:

    @staticmethod
    def classify(query: str) -> str:
        q = query.lower().strip()

        if any(k in q for k in ["my name", "who am i", "my pan", "my tan", "my regime", "my profile", "my status", "what do you know about me", "tell me about myself"]):
            return "IDENTITY"

        if q.startswith(("who is", "what is", "define", "explain")):
            return "DEFINITION"

        # FOLLOW-UP first (more important)
        if any(p in q for p in ["he", "she", "it", "they", "him", "her"]):
            return "FOLLOW_UP"

        if len(q.split()) <= 2:
            return "ENTITY"

        return "GENERAL"