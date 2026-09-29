"""Parsing real mittog.dk snapshots."""

from __future__ import annotations

from datetime import datetime

from custom_components.mittog import stations
from custom_components.mittog.api import TZ, board_url, parse_board, parse_time, upcoming, web_url

from .conftest import load

NOW = datetime(2026, 9, 29, 18, 46, 10, tzinfo=TZ)


def test_parse_time() -> None:
    assert parse_time("29-09-2026 18:46:00") == datetime(2026, 9, 29, 18, 46, tzinfo=TZ)
    assert parse_time("01-01-0001 00:00:00") is None
    assert parse_time(None) is None
    assert parse_time("garbage") is None


def test_urls() -> None:
    assert board_url("stog", "VNG") == "wss://api.mittog.dk/api/ws/stog/departure/VNG/"
    assert board_url("tog", "KH") == "wss://api.mittog.dk/api/ws/departure/KH/dinstation/"
    assert board_url("stog", "ØL") == "wss://api.mittog.dk/api/ws/stog/departure/%C3%98L/"
    assert web_url("stog", "VNG") == "https://mittog.dk/da/departures/VNG/stog/"


def test_stog_board() -> None:
    board = parse_board(load("stog_vng.json"), "VNG")
    assert board.created is not None
    assert len(board.departures) == 6
    first = board.departures[0]
    assert first.line == "C"
    assert first.color == "#F58A1F"
    assert first.destination == "Klampenborg"
    assert first.track == "1"
    assert first.direction == "UP"
    assert first.delay_minutes == 0
    assert "KH" in first.stops and "VNG" not in first.stops
    assert first.calls_at({"KH"})
    towards_fs = [d for d in board.departures if d.calls_at({"FS"})]
    assert len(towards_fs) == 3
    assert all(d.direction == "DOWN" for d in towards_fs)


def test_tog_board() -> None:
    board = parse_board(load("tog_kh.json"), "KH")
    by_number = {d.number: d for d in board.departures}
    ic = by_number["50850"]
    assert ic.line == "IC"
    assert ic.destinations == ["KK"]  # HGL is the feed's alias for Østerport
    assert ic.destination == "Østerport"
    assert ic.delay_minutes == 15
    oresund = by_number["1116"]
    assert oresund.line == "Øresundståg"
    assert oresund.destination == "Hässleholm / Kristianstad / Karlskrona"
    assert not oresund.track_changed  # original and current track are both 6
    assert by_number["52550"].track_changed
    assert by_number["70071"].destination == "Aarhus H / Aalborg"
    assert len(board.notices) == 2 and board.notices[0].urgent

    live = upcoming(board.departures, NOW, 30)
    numbers = {d.number for d in live}
    assert "54250" not in numbers  # already departed
    assert "50173" not in numbers  # 18:45:00, past the grace period
    assert live == sorted(live, key=lambda d: d.expected)


def test_terminating_and_freight_trains_are_hidden() -> None:
    message = load("stog_vng.json")
    trains = message["data"]["Trains"]
    trains[0]["Routes"][0]["DestinationStationId"] = "VNG"
    trains[1]["Product"] = "GD"
    board = parse_board(message, "VNG")
    assert len(board.departures) == 4


def test_catalogue() -> None:
    assert stations.name("VNG") == "Vinge"
    assert stations.get("KH").services == ("stog", "tog")
    assert stations.name("%HM") == "Hässleholm"
    assert stations.name("NOPE") == "NOPE"
    assert all("stog" in s.services for s in stations.for_service("stog"))
