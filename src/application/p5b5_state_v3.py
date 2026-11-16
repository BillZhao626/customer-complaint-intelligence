"""Do not infer selection from discussion of alternatives (v2 remains frozen)."""
import re
from src.application.p5b5_state_v2 import ConversationState as Previous

class ConversationState(Previous):
    def update(self,role,text):
        previous=self.preferred_outcome
        super().update(role,text)
        if role!='customer':return
        if re.search(r'说不准|没决定|未决定|拿不准|不确定|还是|或者|都想先了解|undecided|not sure|repair or|return or',text,re.I):
            self.preferred_outcome=None;return
        def affirmative(pattern):
            for m in re.finditer(pattern,text,re.I):
                if not re.search(r'不|不要|别|not\s*$',text[max(0,m.start()-3):m.start()],re.I):return True
            return False
        if affirmative(r'(?:更想|想|希望|决定|选择|倾向|要)(?:办理)?退(?:货|掉)|prefer (?:to )?return|want (?:a )?refund'):
            self.preferred_outcome='return'
        elif affirmative(r'(?:改成|更想|想|希望|决定|选择|倾向|要)(?:办理)?换货|prefer (?:an )?exchange'):
            self.preferred_outcome='exchange'
        elif re.search(r'不想修|不要维修|不考虑维修|no repair',text,re.I):self.preferred_outcome=previous or 'no_repair'
        else:self.preferred_outcome=previous
