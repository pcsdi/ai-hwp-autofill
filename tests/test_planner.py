from hwp_autofill.planner import canonical, compare_values
def test_alias():
    assert canonical("운영일") == "일시"
    assert canonical("교육 대상") == "대상"
    assert canonical("사업명") == "프로그램명"

def test_action():
    assert compare_values("", "새 값") == "fill"
    assert compare_values("같음", "같음") == "keep"
    assert compare_values("옛 값", "새 값") == "replace"
    assert compare_values("옛 값", "") == "review"
