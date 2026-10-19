"""
Tests for intent classification and out-of-scope detection.
Verifies on-topic questions, document-anchor queries, and graceful out-of-scope identification.
"""
import pytest
from app.rag.intent_classifier import classify_intent, Intent


def test_greetings_out_of_scope():
    assert classify_intent("hi") == Intent.OUT_OF_SCOPE
    assert classify_intent("hello") == Intent.OUT_OF_SCOPE
    assert classify_intent("namaste") == Intent.OUT_OF_SCOPE
    assert classify_intent("ok") == Intent.OUT_OF_SCOPE


def test_off_topic_queries_rejected_for_space_document():
    space_doc = "Astrophysics and Deep Space Exploration"
    
    # Politics should be OUT_OF_SCOPE
    assert classify_intent("Who is the prime minister of India?", document_title=space_doc) == Intent.OUT_OF_SCOPE
    assert classify_intent("What is the election result of BJP and Congress?", document_title=space_doc) == Intent.OUT_OF_SCOPE
    assert classify_intent("rajniti ke baare me batao", document_title=space_doc) == Intent.OUT_OF_SCOPE
    
    # Sports should be OUT_OF_SCOPE
    assert classify_intent("Who won the IPL match yesterday?", document_title=space_doc) == Intent.OUT_OF_SCOPE
    assert classify_intent("cricket match score kya hai", document_title=space_doc) == Intent.OUT_OF_SCOPE
    
    # Recipes / cooking should be OUT_OF_SCOPE
    assert classify_intent("Chicken biryani recipe batao", document_title=space_doc) == Intent.OUT_OF_SCOPE
    
    # Movies / Bollywood should be OUT_OF_SCOPE
    assert classify_intent("Tell me about latest Bollywood movie", document_title=space_doc) == Intent.OUT_OF_SCOPE


def test_on_topic_queries_accepted_for_space_document():
    space_doc = "Astrophysics and Deep Space Exploration"
    
    # Space / physics questions should NOT be out of scope
    assert classify_intent("How do black holes form?", document_title=space_doc) != Intent.OUT_OF_SCOPE
    assert classify_intent("Explain gravitational waves", document_title=space_doc) != Intent.OUT_OF_SCOPE
    assert classify_intent("What is escape velocity?", document_title=space_doc) != Intent.OUT_OF_SCOPE
    assert classify_intent("iska matlab kya hai space me", document_title=space_doc) != Intent.OUT_OF_SCOPE


def test_document_anchored_queries_always_on_topic():
    # Even if mentioning words like vote or minister, if anchored to the book/chapter, it's on-topic
    assert classify_intent("What does the author say in chapter 3 about this?") != Intent.OUT_OF_SCOPE
    assert classify_intent("Book me iske baare me kya likha hai?") != Intent.OUT_OF_SCOPE


def test_document_title_preserves_on_topic():
    # If the document itself is about politics, election questions are on-topic
    politics_doc = "Election Systems and Democracy in Modern Republics"
    assert classify_intent("How does voting work?", document_title=politics_doc) != Intent.OUT_OF_SCOPE
    assert classify_intent("What is the role of parliament in democracy?", document_title=politics_doc) != Intent.OUT_OF_SCOPE


def test_footnote_build_queries_out_of_scope():
    from app.rag.prompts import is_about_footnote_build
    assert is_about_footnote_build("tum kaise build hue ho") == True
    assert is_about_footnote_build("tum kaise bane ho") == True
    assert is_about_footnote_build("who built footnote") == True
    assert is_about_footnote_build("how were you created") == True
    assert is_about_footnote_build("what is gravity") == False

    assert classify_intent("tum kaise build hue ho") == Intent.OUT_OF_SCOPE
    assert classify_intent("who built you?") == Intent.OUT_OF_SCOPE
    assert classify_intent("how was footnote built?") == Intent.OUT_OF_SCOPE

