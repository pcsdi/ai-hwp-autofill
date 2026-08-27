from hwp_autofill.planner import canonical, compare_values

def test_aliases():
    assert canonical("사업명")=="프로그램명"
    assert canonical("운영일")=="일시"
    assert canonical("교육 대상")=="대상"

def test_actions():
    assert compare_values("", "새 값")=="fill"
    assert compare_values("과거","최신")=="replace"
    assert compare_values("같음","같음")=="keep"
    assert compare_values("과거","")=="review"
