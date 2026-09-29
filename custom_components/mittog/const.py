"""Constants for Mittog."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "mittog"

WS_BASE: Final = "wss://api.mittog.dk/api/ws"
WEB_BASE: Final = "https://mittog.dk/da/departures"

SERVICE_STOG: Final = "stog"
SERVICE_TOG: Final = "tog"
SERVICES: Final = (SERVICE_STOG, SERVICE_TOG)

SUBENTRY_STATION: Final = "station"

CONF_SERVICE: Final = "service"
CONF_STATION: Final = "station"
CONF_TOWARDS: Final = "towards"
CONF_LINES: Final = "lines"
CONF_TRACKS: Final = "tracks"
CONF_MAX_DEPARTURES: Final = "max_departures"
CONF_HIDE_CANCELLED: Final = "hide_cancelled"
CONF_DELAY_THRESHOLD: Final = "delay_threshold"

DEFAULT_MAX_DEPARTURES: Final = 10
DEFAULT_DELAY_THRESHOLD: Final = 3

# No message for this long means the board is stale (the server pushes every 10-60 s).
STALE_AFTER: Final = 180
# A departure stays on the board this long after its expected time.
DEPARTED_GRACE: Final = 30

S_TRAIN_LINES: Final = ("A", "B", "Bx", "C", "E", "F", "H")

# Line colours used by mittog.dk / DSB for S-tog lines.
LINE_COLORS: Final = {
    "A": "#00B2EF",
    "B": "#50B848",
    "BX": "#A6CE39",
    "C": "#F58A1F",
    "C1": "#F58A1F",
    "C2": "#F58A1F",
    "E": "#7670B2",
    "F": "#FFC20E",
    "H": "#EF4130",
}

# Regional/long-distance product code -> (label, colour, operator), from mittog.dk.
PRODUCTS: Final = {
    "AL": ("RA", "#6938a1", "GoCollective"),
    "AN": ("RA", "#6938a1", "GoCollective"),
    "AP": ("RA", "#6938a1", "GoCollective"),
    "RA": ("RA", "#6938a1", "GoCollective"),
    "AR": ("RA", "#6938a1", "GoCollective"),
    "AF": ("RA", "#6938a1", "GoCollective"),
    "AE": ("RA", "#6938a1", "GoCollective"),
    "RX": ("Rex", "#aeaeff", "GoCollective"),
    "AX": ("Rex", "#aeaeff", "GoCollective"),
    "RV": ("Re", "#50AE30", "DSB"),
    "RØ": ("Re", "#50AE30", "DSB"),
    "RR": ("Re", "#50AE30", "DSB"),
    "EP": ("Re", "#47A440", "DSB"),
    "IR": ("Re", "#639830", "DSB"),
    "FX": ("Re", "#47A440", ""),
    "ØP": ("Øresundståg", "#50AE30", "VR"),
    "ØR": ("L", "#041E42", "Lokaltog"),
    "ØK": ("L", "#041E42", "Lokaltog"),
    "ØD": ("L", "#041E42", "Lokaltog"),
    "ØF": ("L", "#041E42", "Lokaltog"),
    "ØL": ("L", "#041E42", "Lokaltog"),
    "ØT": ("L", "#041E42", "Lokaltog"),
    "ØX": ("L", "#041E42", "Lokaltog"),
    "LP": ("L", "#041E42", "Lokaltog"),
    "LR": ("L", "#041E42", "Lokaltog"),
    "PP": ("L", "#041E42", "Lokaltog"),
    "SK": ("SK", "#B6B6B6", "DSB"),
    "P": ("P", "#009BF1", ""),
    "IC": ("IC", "#EC3400", "DSB"),
    "IE": ("ICE", "#2A6996", "DSB"),
    "IL": ("ICL+", "#F28596", "DSB"),
    "L": ("ICL", "#FDBA58", "DSB"),
    "JP": ("BTE", "#3F878E", "BTE"),
    "SJ": ("SJ", "#767676", "SJ"),
    "SP": ("RDC/EN", "#767676", "SJ"),
    "EC": ("EC", "#2A6996", "DSB"),
    "EJ": ("RJ", "#2A6996", "DSB"),
    "EX": ("ECE", "#2A6996", "DSB"),
    "IP": ("IP", "#767680", ""),
    "MD": ("MJ", "#9B2310", "Midtjyske Jernbaner"),
    "MR": ("MJ", "#9B2310", "Midtjyske Jernbaner"),
    "MP": ("L", "#041E42", "Midtjyske Jernbaner"),
    "MS": ("L", "#041E42", "Midtjyske Jernbaner"),
    "MZ": ("L", "#041E42", "Midtjyske Jernbaner"),
    "NL": ("RE", "#003087", "Nordjyske Jernbaner"),
    "NR": ("RE", "#003087", "Nordjyske Jernbaner"),
    "NP": ("L", "#041E42", "Nordjyske Jernbaner"),
    "RM": ("L", "#041E42", "Nordjyske Jernbaner"),
    "RN": ("L", "#041E42", "Nordjyske Jernbaner"),
    "HV": ("SJ/EN", "#767676", "Snälltåget"),
    "HP": ("RDC/EN", "#767676", "Hector Rail"),
    "RS": ("ST", "#F2FE50", "Snälltåget"),
    "XP": ("ST", "#F2FE50", "Snälltåget"),
    "VP": ("V", "#B6B6B6", ""),
}

# Freight/engineering products mittog.dk never shows on a departure board.
NON_PASSENGER_PRODUCTS: Final = frozenset(
    {
        "BG", "BM", "BF", "CG", "CM", "CF", "CB", "CX", "HG", "HM", "HF", "HB", "PG", "PM",
        "GL", "GD", "GK", "GX", "G", "GM", "FG", "GB", "TG", "TM", "TF", "RG", "RB", "FW",
        "GF", "FX", "MF", "FB", "M", "FM", "FE", "ØM", "SM", "VM", "AM", "NM",
    }
)
HIDDEN_STOP_TYPES: Final = frozenset(
    {"TechnicalStop", "CommercielDisembarcationOnly", "FinalDestination", "PassThrough"}
)
