from app.services.matcher import parse_user_content, build_matches


def test_parse():
    data = parse_user_content('교육명: AI 진로교육\n대상: 고3\n인원: 8명')
    assert data['교육명'] == 'AI 진로교육'
    assert data['대상'] == '고3'


def test_match():
    ms = build_matches('프로그램명 대상 인원', [], '교육명: AI 진로교육\n대상: 고3\n인원: 8명')
    assert len(ms) == 3
