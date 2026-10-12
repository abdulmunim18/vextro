"""Opinion-risk v1: telling a view of the phone from an advert or a question."""

from datetime import UTC, datetime, timedelta

import pytest

from app.services.opinion_risk_engine import (
    KIND_ABUSIVE,
    KIND_ADVERT,
    KIND_OPINION,
    KIND_QUESTION,
    VERSION,
    OpinionEvidence,
    analyze_opinion,
)


def post(identifier: int, text: str, **details: object) -> OpinionEvidence:
    return OpinionEvidence(id=identifier, text=text, **details)


def analyze(text: str, **details: object) -> dict[str, object]:
    subject = post(1, text, **details)

    return analyze_opinion(subject, [subject])


@pytest.mark.parametrize(
    "text",
    [
        "I want to sell my honor x9d anyone's interested in Karachi then contact me [number removed]",
        "Koi bhai Karachi me sale karna chats ho mujh se rabta kre [number removed]",
        "Honor X9d Forsale ha only 2 month use 10/10 condition whatsapp [number removed].",
        "Agar Kasi ne Hafizabad me seal Karna ho toh rabta kare [number removed]",
        "Samsung Galaxy a27 pinpack available in blue color in just 115k [number removed]",
        "Ye mobile Kisi bhai ne exchange karna ho to mere pass oppo Reno 15f full box [number removed]",
    ],
)
def test_a_sale_advert_with_a_contact_number_is_high_risk(text: str) -> None:
    result = analyze(text, contact_removed=True)

    assert result["opinion_kind"] == KIND_ADVERT
    assert result["suspicion_level"] == "high"
    assert result["analysis_version"] == VERSION
    assert {"contact_number_shared", "trade_offer"} <= set(
        result["applied_weights"]
    )


def test_an_advert_without_a_number_is_still_recognised() -> None:
    result = analyze("Ager kisi ny sell karna h to bata dy")

    assert result["opinion_kind"] == KIND_ADVERT
    assert result["suspicion_level"] == "medium"


def test_a_bare_contact_number_is_an_advert_of_medium_risk() -> None:
    result = analyze("55000.naveed [number removed]", contact_removed=True)

    assert result["opinion_kind"] == KIND_ADVERT
    assert result["suspicion_level"] == "medium"


@pytest.mark.parametrize(
    "text",
    [
        "IPS Display in this expensive phone. Shame on you,",
        "Itna Kuch khas nhi hai phone mei UFS bhi kam hai Fingerprint bhi optical hai. Over price hai.",
        "Koi Bhai ye mobile buy nahi kare iski price jaldi 85 se 90 tak ajayegi",
        "Koi b Infinix k mobile na lay inki after sales service buhat poor hai",
        "battery timing and display is good.",
        "I want to buy this phone, camera bohat acha hai",
    ],
)
def test_a_view_of_the_phone_is_low_risk(text: str) -> None:
    result = analyze(text)

    assert result["opinion_kind"] == KIND_OPINION
    assert result["suspicion_level"] == "low"
    assert result["suspicion_score"] == 0


@pytest.mark.parametrize(
    "text",
    [
        "pakistan me kb aye ga",
        "When it will be launch in Pakistan....?",
        "Ya mobile kab tak markeet main ajay ga please koi bata sakta many buy krna hai",
        "Is phone ki network coverage kesi hai. Indoor/Outdoor 4G/5G signal strength bta de koi",
        "Yeh mobile kasa ha lana chaye ya nahi games kalie",
        "Ksa hai yeh phone use krne mea... Any feedback...",
        "iss ka front camera kitna pixels ka ha i wanna know about it",
    ],
)
def test_a_question_is_named_as_one_and_is_not_suspicious(text: str) -> None:
    result = analyze(text)

    assert result["opinion_kind"] == KIND_QUESTION
    assert result["suspicion_level"] == "low"


def test_the_same_text_posted_again_is_flagged_on_both_posts() -> None:
    day = datetime(2026, 9, 1, tzinfo=UTC)
    text = "Bohat zabardast mobile hai camera aur battery dono kamal"
    posts = [
        post(1, text, author="visitor1", posted_at=day),
        post(2, text.upper(), author="visitor2", posted_at=day + timedelta(days=9)),
        post(3, "Display IPS hai is qeemat mein AMOLED honi chahiye thi", posted_at=day),
    ]

    first, second, third = (analyze_opinion(item, posts) for item in posts)

    assert "exact_duplicate" in first["applied_weights"]
    assert "exact_duplicate" in second["applied_weights"]
    assert first["suspicion_level"] == "medium"
    assert third["suspicion_score"] == 0
    # Copied wording is suspicious, but it is still about the phone.
    assert first["opinion_kind"] == KIND_OPINION


def test_a_burst_of_copies_from_one_name_is_high_risk() -> None:
    day = datetime(2026, 9, 1, tzinfo=UTC)
    text = "Best phone in this price range, everyone should buy it today"
    posts = [
        post(index, text, author="promo", posted_at=day + timedelta(hours=index))
        for index in range(1, 4)
    ]

    result = analyze_opinion(posts[0], posts)

    assert {
        "exact_duplicate",
        "similar_post_burst",
        "repeated_author_wording",
    } <= set(result["applied_weights"])
    assert result["suspicion_level"] == "high"


def test_every_score_comes_with_a_reason_a_person_can_read() -> None:
    advert = analyze("I want to sale urgently [number removed]", contact_removed=True)
    clean = analyze("Camera acha hai lekin charging slow hai")

    assert len(advert["reasons"]) == 2
    assert all(isinstance(reason, str) and reason for reason in advert["reasons"])
    assert clean["reasons"] == [
        "No configured pattern was found; it reads as a view of the phone."
    ]


def test_an_insult_aimed_at_a_person_is_named_abusive() -> None:
    result = analyze("Mushtaq Ahmad Your Illegal Father OPPO is providing 6 Gen 1 in 135K.")

    assert result["opinion_kind"] == KIND_ABUSIVE
    assert result["suspicion_level"] == "medium"


@pytest.mark.parametrize(
    "text",
    [
        "Vivo ghitya tareen company, bakwas mobile hai",
        "Bkawas phone third class specifications please don't waste money",
    ],
)
def test_harsh_words_about_the_phone_are_still_an_opinion(text: str) -> None:
    assert analyze(text)["opinion_kind"] == KIND_OPINION
