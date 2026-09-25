import pytest
from app.rag.prompts import wants_detail

def test_wants_detail():
    # Mock test for wants_detail
    # English + Hinglish + Devanagari
    
    assert wants_detail("Can you explain this in detail?") == True
    assert wants_detail("aur samjhao") == True
    assert wants_detail("विस्तार से") == True
    assert wants_detail("what is the capital of france?") == False
