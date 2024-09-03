from datetime import datetime
import re


def date_easy_typing(date):
    """日期输入简化
    输出格式要求：yyyy-mm-dd
    输入格式：dd, yyyy-mm-dd, mm-dd, yyyy/mm/dd, mm/dd, yyyy\mm\dd, mm\dd
    """
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")
    elif isinstance(date, str):
        # 可能分隔符为-/\
        separator = r"[-/\\]"
        ymd = re.split(separator, date)
        if len(ymd) == 3:
            # yyyy-mm-dd
            dt = datetime(*map(int, ymd))
        elif len(ymd) == 2:
            # mm-dd
            dt = datetime(datetime.now().year, *map(int, ymd))
        elif len(ymd) == 1:
            # dd
            dt = datetime(datetime.now().year, datetime.now().month, int(ymd[0]))
        else:
            raise ValueError(f"日期格式错误：{date}")
        date = dt.strftime("%Y-%m-%d")
    else:
        raise ValueError(f"日期格式错误：{date}")
    return date


def separator_unify(seats):
    """座位/车次输入简化
    输出格式要求：空格分隔的座位类型
    输入格式：空格、逗号、分号、中文逗号、中文分号分隔的座位类型
    """
    if not seats:
        return seats
    separator = r"[\s,;，；]"
    return " ".join(re.split(separator, seats))


def test():
    assert date_easy_typing("1") == "%d-%02d-01" % datetime.now().timetuple()[:2]
    assert date_easy_typing("2024-05-01") == "2024-05-01"
    assert date_easy_typing("05-01") == "%d-05-01" % datetime.now().year
    assert date_easy_typing("2024/05/01") == "2024-05-01"
    assert date_easy_typing("05/01") == "%d-05-01" % datetime.now().year
    assert date_easy_typing(r"2024\05\01") == "2024-05-01"
    assert date_easy_typing(r"05\01") == "%d-05-01" % datetime.now().year

    assert separator_unify("商务座") == "商务座"
    assert separator_unify("商务座 一等座") == "商务座 一等座"
    assert separator_unify("商务座,一等座") == "商务座 一等座"
    assert separator_unify("商务座;一等座") == "商务座 一等座"
    assert separator_unify("商务座，一等座") == "商务座 一等座"
    assert separator_unify("商务座；一等座") == "商务座 一等座"
    print("测试通过")


if __name__ == "__main__":
    import fire

    fire.Fire()
