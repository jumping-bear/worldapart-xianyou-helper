# -*- coding: utf-8 -*-
"""拍卖会：本场拍品、珍匣、寄售与竞拍参考。"""

from .build import build
from .scan import builtin_ok, empty, enrich, meta, scan, summary

KEY, LABEL = "auction", "拍卖会"
KEY, LABEL_EN = "auction", "Auction"
ORDER, SELECT, SCHEMA = 92, "latest", 1
SNAPSHOT = "auction_meta.json"
TABLES = frozenset({
    "tbauctionvenue", "tbauctionitempool", "tbauctiontactic", "tbauctionloan",
    "tbauctionhermit", "tbauctionchestconfig",
    "tbitem", "tbitemtype", "tbcultivaterealm",
})
