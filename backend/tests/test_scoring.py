from app.scoring import interview_confidence, matched_people_for_video, parse_youtube_duration, people_signals_for_video, priority_score


def test_parse_youtube_duration() -> None:
    assert parse_youtube_duration("PT1H02M03S") == 3723
    assert parse_youtube_duration("PT47M") == 2820
    assert parse_youtube_duration("") == 0


def test_interview_confidence_prefers_long_form_interviews() -> None:
    score = interview_confidence("Founder interview full episode", "A long conversation", 2400)
    short_score = interview_confidence("Product launch shorts", "short clip", 50)
    assert score > 0.7
    assert short_score < score


def test_people_matching_and_priority_score() -> None:
    people = [{"name": "Sam Altman", "english_name": "", "aliases": "OpenAI", "priority": 5}]
    matches = matched_people_for_video("Sam Altman interview", "OpenAI strategy", people)
    assert len(matches) == 1
    assert priority_score(matches, 0.9, "2026-06-13T00:00:00+00:00", "Decoder", 100000) > 75


def test_org_alias_does_not_match_person_without_name() -> None:
    people = [{"name": "Sam Altman", "english_name": "", "aliases": "OpenAI", "priority": 5}]
    matches = matched_people_for_video("OpenAI launches a new product", "A discussion of AI strategy", people)
    assert matches == []


def test_candidate_guest_is_extracted_from_metadata() -> None:
    _, matched_names, candidate_people, reason = people_signals_for_video(
        "AI Is Not a Strategy: How to Lead Real Transformation with Julie Averill",
        "John sits down with Julie Averill, founder of Gold Thread and former CIO of lululemon.",
        "John Barrows",
        [],
    )
    assert matched_names == ""
    assert candidate_people == "Julie Averill"
    assert "识别" in reason


def test_mentioned_tracked_person_is_not_treated_as_guest() -> None:
    people = [{"name": "Sam Altman", "english_name": "", "aliases": "OpenAI, Altman", "priority": 5}]
    description = (
        "In this episode, we sit down with JD Ross, founder of Open Door and now WithCoverage, "
        "to break down why domain expertise plus AI tools wins. We unpack why he turned down "
        "Sam Altman's offer to run OpenAI's business side."
    )
    matches, matched_names, candidate_people, reason = people_signals_for_video(
        "$8B Founder: What AI Founders Know That You Don't - JD Ross",
        description,
        "Natalie Dawson",
        people,
    )
    assert matches == []
    assert matched_names == ""
    assert candidate_people == "JD Ross"
    assert "识别" in reason
