"""Additive state correction: an undecided question is not a return preference."""
import re
from src.application.p5b5_pipeline import ConversationState as Previous

class ConversationState(Previous):
    def update(self,role,text):
        super().update(role,text)
        if role!='customer':return
        if re.search(r'说不准|没决定|未决定|拿不准|不确定|退还是换|undecided|not sure',text,re.I):
            self.preferred_outcome=None
        # Identifiers reported by customers only, including historical non-DEMO prefixes.
        self.identifiers=list(dict.fromkeys(self.identifiers+re.findall(r'\b[A-Z]{1,6}-[A-Z0-9-]+\b',text)))
