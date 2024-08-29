#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
@author: HJK
@file: train.py
@time: 2019-02-08
"""
"""
    搜索结果中的班次信息
"""

import time
import re
import requests
import prettytable as pt

from .settings import settings
from .utils import colorize


class Train:
    """
    搜索结果中的班次信息，包括车次号、余票、时间等信息
    """

    def __init__(self):
        self.full_no = ""  # 编号全称
        self.no = ""  # 编号简称
        self._fs_code = ""
        self._ts_code = ""
        self._fs = ""
        self._ts = ""
        self.start_time = ""
        self.end_time = ""
        self.duration = ""
        self.remaining = []

    def __str__(self):
        colored_remaining = [
            colorize(s, "green") if s != "无" and s != "--" else s
            for s in self.remaining
        ]
        remaining_seats = "/".join(colored_remaining)
        if re.match("[GCD]", self.no):
            colored_no = colorize(self.no, self.no[0].lower())
        else:
            colored_no = colorize(self.no, "o")
        s = "{:^5} | {:^5} | {:\u3000<4} | {:\u3000<4} | {:^5} | {} | {:^5}".format(
            colored_no,
            self.start_time,
            self._fs,
            self._ts,
            self.end_time,
            remaining_seats,
            self.duration,
        )
        return s

    def __eq__(self, other):
        """车次、出发站和目的地相同判断为相等"""
        return (
            self.full_no == other.full_no
            and self._fs == other._fs
            and self._ts == other._ts
        )
    
    def __hash__(self) -> int:
        return hash((self.full_no, self._fs, self._ts))

    def __lt__(self, other):
        """根据车次号排序"""
        return self.start_time < other.start_time

    def __gt__(self, other):
        """根据车次号排序"""
        return self.start_time > other.start_time

    @property
    def fs_code(self):
        return self._fs_code

    @fs_code.setter
    def fs_code(self, fs_code):
        self._fs_code = fs_code
        self._fs = settings.reverse_stations_dict.get(fs_code, "")

    @property
    def ts_code(self):
        return self._ts_code

    @ts_code.setter
    def ts_code(self, ts_code):
        self._ts_code = ts_code
        self._ts = settings.reverse_stations_dict.get(ts_code, "")

    @property
    def has_remaining(self) -> bool:
        for r in self.remaining:
            if r != "无" and r != "--":
                return True
        return False

    @property
    def row(self) -> list:
        """关键信息列表"""
        colored_remaining = [
            colorize(s, "green") if s != "无" and s != "--" else s
            for s in self.remaining
        ]
        remaining_seats = "/".join(colored_remaining)
        if re.match("[GCD]", self.no):
            colored_no = colorize(self.no, self.no[0].lower())
        else:
            colored_no = colorize(self.no, "o")
        return [
            colored_no,
            self.start_time,
            self._fs,
            self._ts,
            self.end_time,
            remaining_seats,
            self.duration,
        ]
    
    def check_time(self, ttime:str, time_range:str) -> bool:
        """检查发车时间是否符合要求，放在此类中用于对各种模式下的复用
        :param ttime: 发车时间或到达时间, 格式为"HH:MM"
        :param time_range: 时间范围字符串，如"12:00-18:00"，分隔符可以是逗号、分号、空格或短横线
        """
        separators = "[,; -]"  # comma, semicolon, space or hyphen
        fts = re.split(separators, time_range)
        ft_start = fts[0] if len(fts) > 0 else "00:00"
        ft_end = fts[1] if len(fts) > 1 else "24:00"
        if ft_start > ft_end:
            # 跨天
            return ttime >= ft_start or ttime <= ft_end
        else:
            return ft_start <= ttime <= ft_end


class TrainTable:
    """
    搜索结果列表
    """

    def __init__(self):
        self.trains_list = []
        self._session = requests.Session()
        self._session.headers.update(settings.headers)

    @property
    def session(self):
        # TODO: 设置代理、随机headers等
        return self._session

    def echo(self):
        """
        对外调用的方法，用来打印查询结果
        """
        tb = pt.PrettyTable()
        tb.field_names = ["车次", "发车", "出发站", "到达站", "到达", "余票", "历时"]
        self.cleanup()
        for train in self.trains_list:
            tb.add_row(train.row)
        print(tb)

    def cleanup(self):
        """处理trains_list，排序和删除无效数据"""
        t_list = []
        if settings.remaining:
            for train in self.trains_list:
                # print(train.no, train.remaining, train.has_remaining)
                if train.has_remaining:
                    t_list.append(train)
        else:
            t_list = self.trains_list
        # 过滤发车时间
        if settings.ft:
            t_list = [t for t in t_list if t.check_time(t.start_time, settings.ft)]
        # 过滤到达时间
        if settings.tt:
            t_list = [t for t in t_list if t.check_time(t.end_time, settings.tt)]
        # 同城站点过滤
        if not settings.all_stations_in_city:
            t_list = [t for t in t_list if t._fs in settings.station_list("fs")]
            t_list = [t for t in t_list if t._ts in settings.station_list("ts")]
        self.trains_list = sorted(t_list)

    def update(self):
        """
        对外调用的方法，查询12306列车信息，把结果更新到trains_list中
        """
        if settings.zmode:
            self.trains_list = self._query_trains_multi_stations_zmode(
                settings.station_code_list("fs"),
                settings.station_code_list("ts"),
                settings.date,
                settings.trains_no_list,
            )
        else:
            self.trains_list = self._query_trains_multi_stations(
                settings.station_code_list("fs"),
                settings.station_code_list("ts"),
                settings.date,
                settings.trains_no_list,
            )

    def _query(self, url, params, retries=1) -> dict:
        """
            查询方法，根据url和参数，返回json对象
        :param url: 查询url
        :param params: 查询参数
        :param retries: 重试次数
        :return: 返回json对象
        """
        s = self.session
        # print("查询中...", " ".join([v for v in params.values()]))

        try:
            r = s.get(url, params=params, timeout=settings.timeout)
            j = r.json()
            if settings.verbose:
                print(url, params)
                print('\n[REQUEST HEADERS]', s.headers)
                print('\n[RESPONSE HEADERS]', r.headers)
                print('\n[RESPONSE TEXT]', r.text)
        except Exception as e:
            print(colorize("第 %i 查询失败" % retries, "red"), e)
            print(url, params)
            print(s.headers)
            if retries < settings.max_retries:
                time.sleep(retries * settings.timeout)
                return self._query(url, params, retries + 1)
            else:
                j = {}
        return j

    def _query_stations(self, train) -> list:
        """
            查询沿途车站信息
        :param train: Train对象
        """
        stations_list = []
        # 准备请求参数
        params = {
            "train_no": train.full_no,
            "from_station_telecode": train.fs_code,
            "to_station_telecode": train.ts_code,
            "depart_date": settings.date,
        }
        j = self._query(settings.trainno_url, params)
        if j and j.get("data") and j["data"].get("data"):
            for item in j["data"]["data"]:
                if item["isEnabled"]:
                    stations_list.append(item["station_name"])
            stations_list = stations_list[1:-1]  # 除了出发站和目标站本身
        return stations_list

    def _query_trains(self, fs_code, ts_code, date, trains_no_list) -> list:
        """
            普通查询方法，根据出发地和目的地编码、日期和限制车次，返回trains列表
            仅被内部调用，调用前处理好参数
        :param fs_code: 出发地编码
        :param ts_code: 目的地编码
        :param date: 日期
        :param trains_no_list: 选择车次列表
        :return: 返回搜索结果列表，每一项是一个Train对象
        """
        # 准备请求参数
        params = {
            "leftTicketDTO.train_date": date,
            "leftTicketDTO.from_station": fs_code,
            "leftTicketDTO.to_station": ts_code,
            "purpose_codes": "ADULT",
        }
        trains_list = []
        j = self._query(settings.query_url, params)
        if j and j.get("data") and j["data"].get("result"):
            raws = j["data"]["result"]
            # 处理返回结果
            for raw in raws:
                fields = raw.split("|")
                # 如果限制了车次，且搜索车次不在目标车次中则丢弃
                if trains_no_list and fields[3] not in trains_no_list:
                    continue
                if settings.gcd and fields[3][0] not in "GCD":
                    # 只看高铁动车城际
                    continue
                if settings.ktz and fields[3][0] in "GCD":
                    # 只看普通列车
                    continue

                train = Train()
                train.full_no = fields[2]  # 编号全称
                train.no = fields[3]  # 编号简称
                train.fs_code = fields[6]
                train.ts_code = fields[7]
                train.start_time = fields[8]
                train.end_time = fields[9]
                train.duration = fields[10]
                for i in settings.seats_code_list:
                    train.remaining.append(fields[i] or "--")
                trains_list.append(train)
        return trains_list

    def _query_trains_zmode(self, fs_code, ts_code, date, trains_no_list) -> list:
        """
            高级查询模式，会查询从出发站到沿途所有站的车次情况
            仅被内部调用，调用前处理好参数
        :param fs_code: 出发地编码
        :param ts_code: 目的地编码
        :param date: 日期
        :param trains_no_list: 限制车次
        :return: Train对象列表
        """
        trains_list = self._query_trains(fs_code, ts_code, date, trains_no_list)
        trains_no_list = [train.no for train in trains_list]
        stations_list = []

        for train in trains_list:
            stations_list += self._query_stations(train)
        stations_list = list(set(stations_list))

        for station in stations_list:
            ts_code = settings.stations_dict.get(station, "")
            if ts_code:
                trains_list += self._query_trains(
                    fs_code, ts_code, date, trains_no_list
                )

        return list(set(trains_list))
    
    def _query_trains_multi_stations(self, fs_code, ts_code, date, trains_no_list) -> list:
        """
            查询多个站点之间的车次信息, 对query_trains的扩展
        """
        trains_list = []
        for fc in fs_code:
            for tc in ts_code:
                trains_list += self._query_trains(fc, tc, date, trains_no_list)
        return trains_list
    
    def _query_trains_multi_stations_zmode(self, fs_code, ts_code, date, trains_no_list) -> list:
        """
            查询多个站点之间的车次信息, 对query_trains_zmode的扩展
        """
        trains_list = []
        for fc in fs_code:
            for tc in ts_code:
                trains_list += self._query_trains_zmode(fc, tc, date, trains_no_list)
        return trains_list


class CModeTrainTable(TrainTable):
    def __init__(self):
        super().__init__()

    def echo(self):
        """
        对外调用的方法，用来打印查询结果
        """
        if not settings.cmode:
            return super().echo()
        tb = pt.PrettyTable()
        tb.field_names = ["编号", "车次", "发车", "出发站", "到达站", "到达", "余票", "历时", "换乘间隔"]
        self.cleanup()
        for idx, change_train in enumerate(self.trains_list):
            train1, train2, interval = change_train
            tb.add_row([idx, *train1.row, ""])
            tb.add_row(["" ,*train2.row, interval])
        print(tb)

    def cleanup(self):
        """处理trains_list，排序和删除无效数据"""
        if not settings.cmode:
            return super().cleanup()
        t_list = []
        if settings.remaining:
            for train1, train2, interval in self.trains_list:
                # print(train.no, train.remaining, train.has_remaining)
                if train1.has_remaining and train2.has_remaining:
                    t_list.append([train1, train2, interval])
        else:
            t_list = self.trains_list
        # 过滤发车时间
        if settings.ft:
            t_list = [t for t in t_list if t[0].check_time(t[0].start_time, settings.ft)]
        # 过滤到达时间
        if settings.tt:
            t_list = [t for t in t_list if t[1].check_time(t[1].end_time, settings.tt)]
        # 过滤换乘时间
        if settings.ct:
            t_list = [t for t in t_list if t[1].check_time(t[1].start_time, settings.ct)]
        # 同城站点过滤
        if not settings.all_stations_in_city:
            t_list = [t for t in t_list if t[0]._fs == settings.fs]
            t_list = [t for t in t_list if t[0]._ts == settings.cs]
            t_list = [t for t in t_list if t[1]._fs == settings.cs]
            t_list = [t for t in t_list if t[1]._ts == settings.ts]
        self.trains_list = sorted(t_list)        

    def update(self):
        """
        对外调用的方法，查询12306列车信息，把结果更新到trains_list中
        """
        if settings.cmode:
            self.trains_list = self._query_trains_cmode(
                settings.fs_code,
                settings.ts_code,
                settings.cs_code,
                settings.date,
                settings.trains_no_list,
            )
        else:
            return super().update()

    def _query_trains_cmode(self, fs_code, ts_code, cs_code, date, trains_no_list) -> list:
        """
            中转查询
            仅被内部调用，调用前处理好参数
        :param fs_code: 出发地编码
        :param ts_code: 目的地编码
        :param cs_code: 中转站编码
        :param date: 日期
        :param trains_no_list: 限制车次
        :return: Train对象列表
        """
        def convert_digit_to_hm(sec, flag=False):
            sec = 3600 * sec
            m, s = divmod(sec, 60)
            h, m = divmod(m, 60)
            if flag:
                h += 24
            return "%02d:%02d" % (h, m)

        trains_list1 = self._query_trains(fs_code, cs_code, date, trains_no_list)
        trains_list2 = self._query_trains(cs_code, ts_code, date, trains_no_list)
        trains_list = []
        change_interval = settings.ci
        for train1 in trains_list1:
            for train2 in trains_list2:
                time1 = time.strptime(train1.end_time, "%H:%M")
                time2 = time.strptime(train2.start_time, "%H:%M")
                time1 = time1[:0] + (2024,) + time1[1:]
                time2 = time2[:0] + (2024,) + time2[1:]
                diff = (time.mktime(time2) - time.mktime(time1)) / 3600
                if diff > 0 and diff < change_interval:
                    # 当天换乘
                    trains_list.append((train1, train2, convert_digit_to_hm(diff)))
                elif diff < 0 and (diff < -24 + change_interval):
                    # 跨天换乘
                    trains_list.append((train1, train2, convert_digit_to_hm(diff, True)))
        return trains_list
