# Mittog for Home Assistant

Live train departures from [mittog.dk](https://mittog.dk/da/departures/VNG/stog/) in Home Assistant: S-tog and regional/long-distance trains (DSB, Øresundståg, Lokaltog, Arriva …) for any Danish station.

- **As many stations as you like**, each with its own device and sensors.
- **Directions**: pick the direction you travel in from the directions trains actually leave your station in, e.g. *Vinge → København H*. Add the same station again to follow the other direction separately.
- **Search**: one searchable list of every station and board, e.g. *Vinge (S-tog)* or *København H (Tog)*.
- Optional filters (**must stop at**, **line / train type**, **track**). Each offers only what runs in your direction.
- **Live push**: mittog.dk pushes a new board every 10–60 seconds over a WebSocket; nothing is polled. Stations watched with several directions share one connection.
- Delays, cancellations, track changes and station notices ("Meddelelser") from mittog.dk.
- No account or API key needed.
- English and Danish translations.

> Unofficial. This integration is not made by or affiliated with DSB, Banedanmark or mittog.dk. It reads the same public live feed the mittog.dk website uses, and it can break if they change that feed.

---

## 1. Install

### With HACS (recommended)

1. In Home Assistant open **HACS**.
2. Top-right **⋮** → **Custom repositories**.
3. Repository: `https://github.com/TheRealBatBro/Home-Assistant-Mittog`, type **Integration** → **Add**.
4. Search for **Mittog** in HACS, open it and click **Download**.
5. **Restart Home Assistant** (Settings → System → ⏻ → Restart).

### Manually

1. Download this repository (Code → Download ZIP).
2. Copy the folder `custom_components/mittog` into your Home Assistant `config/custom_components/` folder, so you have `config/custom_components/mittog/manifest.json`.
3. Restart Home Assistant.

Requires Home Assistant **2025.10** or newer.

---

## 2. Add your first station

Go to **Settings → Devices & services → + Add integration** and search for **Mittog**. Adding a station takes three short steps.

### Step 1: Station

Start typing the name of the station you travel **from**, e.g. `vinge`, and pick it from the list.

Every station is listed once per departure board:

- **(S-tog)**: the Copenhagen S-trains (lines A, B, Bx, C, E, F, H), e.g. *Vinge (S-tog)*.
- **(Tog)**: regional and long-distance trains (DSB Re/IC/ICL, Øresundståg, Lokaltog, Arriva, Nordjyske …), e.g. *Roskilde (Tog)*.

Big stations such as København H, Østerport, Nørreport, Hellerup, Høje Taastrup and Køge appear twice, as *København H (S-tog)* and *København H (Tog)*. Pick the one for the train you take. See also [Finding the right station](#finding-the-right-station).

### Step 2: Direction

Mittog reads the live board for your station and lists the directions trains actually leave in. Each direction is named after where the trains are going, for example at Vinge:

- *Towards Klampenborg, Svanemøllen · via København H · next stop Ølstykke*
- *Towards Frederikssund*
- *Both directions*

Pick the one you travel in. A direction includes **every** train going that way, including trains that turn back early. In the evening, for example, the C line from Vinge ends at Svanemøllen instead of Klampenborg, and those trains are still shown.

### Step 3: Filters (all optional)

These lists only contain what actually runs from your station **in the direction you picked**:

- **Must stop at**: only trains that stop at one of these stations, in route order (nearest first). Use it to skip trains that end before your stop. Leave it empty in most cases.
- **Lines / train types**: e.g. `A` and `E`, or `IC` and `ICL`.
- **Tracks**: only trains from these tracks.
- **Departures to keep**: how many upcoming departures go into the `departures` attribute (default 10).
- **Delay threshold**: the *Disruption* sensor turns on when a shown train is at least this many minutes late, or cancelled (default 3).
- **Hide cancelled departures**: leave cancelled trains out entirely instead of flagging them.

Press **Submit**. You now have a *Mittog* integration with one station, e.g. **Vinge → København H**.

> The direction and filter choices come from the trains on the board right now (usually the next hour). At night, when the board can be empty, the directions are shown as *Direction 1 / Direction 2*. You can pick one anyway, or come back during the day and edit the station with the pencil.

## 3. Add more stations or the other direction

Open **Settings → Devices & services → Mittog** and click **+ Add station** (top right). Starting again from **+ Add integration → Mittog** or **Devices → + Add device → Mittog** works too: the station is added to your existing Mittog. The steps are the same as above.

| You want | Add |
| --- | --- |
| Your morning train into town | *Vinge (S-tog)* → *Towards … via København H* |
| The way home | *København H (S-tog)* → *Towards Frederikssund …* |
| Both directions at your station, as separate sensors | *Vinge (S-tog)* twice, once per direction |
| Only IC/ICL trains west from Copenhagen | *København H (Tog)* → the direction towards Odense/Fredericia → lines `IC`, `ICL` |
| Only trains that reach your stop | Your station → your direction → **Must stop at** your stop |
| Everything from one platform | *Roskilde (Tog)* → *Both directions* → track `1` |

Each station becomes its own device with its own sensors. Adding the exact same station, direction and filters twice is refused.

**Change** a station's direction or filters: click the **✏️ pencil** next to it on the Mittog page.
**Remove** a station: click **⋮** next to it → **Delete**.
**Change the station itself**: delete it and add the new one.

> **Upgrading from 1.0.0?** Stations added with 1.0.0 used "Towards" stations as the direction. That drops trains that turn back early, e.g. *Vinge → Klampenborg* showed nothing in the evening. Click the pencil, pick the direction and press Submit: the old towards filter is removed automatically.

---

## Finding the right station

**By name.** Type part of the name in the Station field; the list filters as you type and shows which board each entry is. If a station is missing with *(S-tog)*, it has no S-tog board. Aalborg, for example, only exists as *Aalborg (Tog)*.

**By the mittog.dk address.** Open [mittog.dk](https://mittog.dk), find your station and look at the address bar:

```
https://mittog.dk/da/departures/VNG/stog/
                                ^^^ ^^^^
                        station code  board (stog = S-tog, tog = Tog)
```

Type the code (here `VNG`, which is **Vinge**) into the Station field and choose **Add custom item "VNG"**. Codes are not always obvious (Nørreport is `KN`, København H is `KH`, Østerport is `KK`). A code that exists on both boards (like `KH`) picks the S-tog board, so use the list entry *København H (Tog)* for regional trains.

**Picking the direction.** The direction list comes from the live board, so you choose from what is actually there. If you care about one particular stop further along a line that splits, pick the direction and then add that stop under **Must stop at**. For example, *København H (S-tog)* → *Towards Hillerød …* → must stop at *Hillerød* gives you the A and E trains that run all the way.

<details>
<summary>All S-tog stations and their codes</summary>

| Station | Code | |
| --- | --- | --- |
| Albertslund | `ALB` | |
| Allerød | `LI` | |
| Avedøre | `AVØ` | |
| Bagsværd | `BAV` | |
| Ballerup | `BA` | |
| Bernstorffsvej | `BFT` | |
| Birkerød | `BI` | |
| Bispebjerg | `BIT` | |
| Brøndby Strand | `BSA` | |
| Brøndbyøster | `BØT` | |
| Buddinge | `BUD` | |
| Carlsberg | `CB` | |
| Charlottenlund | `CH` | |
| Danshøj | `DAH` | |
| Dybbølsbro | `DBT` | |
| Dyssegård | `DYT` | |
| Egedal | `EGD` | |
| Emdrup | `EMT` | |
| Farum | `FM` | |
| Favrholm | `FVT` | |
| Flintholm | `FL` | |
| Frederikssund | `FS` | |
| Friheden | `FRH` | |
| Fuglebakken | `FUT` | |
| Gentofte | `GJ` | |
| Glostrup | `GL` | |
| Greve | `GRE` | |
| Grøndal | `GHT` | |
| Hareskov | `HAR` | |
| Hellerup | `HL` | also Tog |
| Herlev | `HER` | |
| Hillerød | `HI` | |
| Holte | `HOT` | |
| Hundige | `UND` | |
| Husum | `HUT` | |
| Hvidovre | `HIT` | |
| Høje Taastrup | `HTÅ` | also Tog |
| Ishøj | `IH` | |
| Islev | `IST` | |
| Jersie | `JSI` | |
| Jyllingevej | `JYT` | |
| Jægersborg | `JÆT` | |
| Karlslunde | `KLU` | |
| KB Hallen | `KBN` | |
| Kildebakke | `KET` | |
| Kildedal | `KID` | |
| Klampenborg | `KL` | also Tog |
| København H | `KH` | also Tog |
| København Syd | `NEL` | also Tog |
| Køge | `KJ` | also Tog |
| Køge Nord | `KJN` | also Tog |
| Langgade | `VAT` | |
| Lyngby | `LY` | |
| Malmparken | `MPT` | |
| Måløv | `MW` | |
| Nordhavn | `NHT` | |
| Nørrebro | `NØ` | |
| Nørreport | `KN` | also Tog |
| Ordrup | `OP` | |
| Peter Bangs Vej | `PBT` | |
| Ryparken | `RYT` | |
| Rødovre | `RDO` | |
| Sjælør | `SJÆ` | |
| Skovbrynet | `SKT` | |
| Skovlunde | `SKO` | |
| Solrød Strand | `SOL` | |
| Sorgenfri | `SFT` | |
| Stengården | `SGT` | |
| Stenløse | `ST` | |
| Svanemøllen | `SAM` | |
| Sydhavn | `SYV` | |
| Taastrup | `TÅ` | |
| Valby | `VAL` | also Tog |
| Vallensbæk | `VLB` | |
| Vangede | `ANG` | |
| Vanløse | `VAN` | |
| Veksø | `VS` | |
| Vesterport | `VPT` | |
| Vigerslev Allé | `VGT` | |
| Vinge | `VNG` | |
| Virum | `VIR` | |
| Værløse | `VÆR` | |
| Ålholm | `ÅLM` | |
| Åmarken | `ÅM` | |
| Ølby | `ØLB` | also Tog |
| Ølstykke | `ØL` | |
| Østerport | `KK` | also Tog |

</details>

The regional train stations (about 250) are in [`stations.json`](custom_components/mittog/stations.json). Each code is listed with its name and boards.

---

## Entities

Each station (device) gets these entities. Entity IDs follow the device name, e.g. `sensor.vinge_kobenhavn_h_next_departure`. With Home Assistant in Danish the names are in Danish, e.g. *Næste afgang*.

| Entity | State | Useful attributes |
| --- | --- | --- |
| **Next departure** (*Næste afgang*) | Time of the next train that is not cancelled (timestamp, delays included) | `line`, `destination`, `track`, `delay`, `minutes`, `cancelled`, `scheduled`, `expected`, `train_number`, `operator`, `color`, `via`, `original_track` (track change), `direction` (`UP`/`DOWN`, or empty for both), and **`departures`**: the list of upcoming departures, each with the same fields |
| **Following departure** (*Efterfølgende afgang*) | Time of the train after that | same per-train fields |
| **Minutes to departure** (*Minutter til afgang*) | Whole minutes until the next train | |
| **Delay** (*Forsinkelse*) | Delay of the next train, in minutes | |
| **Notices** (*Meddelelser*) | Number of station notices from mittog.dk | `notices`: `header`, `body`, `urgent` |
| **Disruption** (*Driftsforstyrrelse*) | On if a shown train is cancelled or at least the threshold late | `cancelled`, `delayed`, `affected` |
| **Live connection** (*Live-forbindelse*, diagnostic) | On while the live feed is connected | |

A train stays on the board for 30 seconds after its expected departure. If mittog.dk sends nothing for 3 minutes, the sensors become *unavailable* until the feed is back. The integration reconnects by itself.

---

## Dashboard examples

**Departure board** (Markdown card; change the entity ID):

```yaml
type: markdown
title: Vinge → København H
content: >
  {% set deps = state_attr('sensor.vinge_kobenhavn_h_next_departure', 'departures') or [] %}
  | | Til | Spor | Afgang | |
  |---|---|---|---|---|
  {% for d in deps[:6] -%}
  | **{{ d.line }}** | {{ d.destination }} | {{ d.track }} | {{ as_timestamp(d.expected) | timestamp_custom('%H:%M') }} ({{ d.minutes }} min) | {% if d.cancelled %}❌ Aflyst{% elif d.delay > 0 %}+{{ d.delay }} min{% endif %} |
  {% endfor %}
```

**Tile for the next train**:

```yaml
type: tile
entity: sensor.vinge_kobenhavn_h_next_departure
```

**Notify me when my morning train is late or cancelled**:

```yaml
alias: Train disruption
triggers:
  - trigger: state
    entity_id: binary_sensor.vinge_kobenhavn_h_disruption
    to: "on"
conditions:
  - condition: time
    after: "06:30:00"
    before: "09:00:00"
    weekday: [mon, tue, wed, thu, fri]
actions:
  - action: notify.notify
    data:
      message: >
        {% set t = state_attr('binary_sensor.vinge_kobenhavn_h_disruption', 'affected')[0] %}
        {{ t.line }} to {{ t.destination }} {{ as_timestamp(t.scheduled) | timestamp_custom('%H:%M') }}:
        {{ 'cancelled' if t.cancelled else '+' ~ t.delay ~ ' min' }}
```

---

## Troubleshooting

- **Sensors are *unknown***: no train on the board matches your direction and filters right now (for example at night, or because a filter is too tight). The board covers roughly the next hour. Check the unfiltered board on mittog.dk: the device page has a *Visit* link to it.
- **Sensors are *unavailable***: the feed has been silent for 3 minutes. Check *Live connection*. It reconnects by itself, backing off up to 5 minutes.
- **A train you expected is missing**: check the direction and, if you set one, the *Must stop at* filter. With *Must stop at*, a train is only shown if it stops at one of those stations after yours. Trains that turn back early don't, so leave that filter empty unless you need it. Trains that terminate at your station are arrivals and are never shown.
- **Debug logging**:

  ```yaml
  logger:
    logs:
      custom_components.mittog: debug
  ```

  **Settings → Devices & services → Mittog → ⋮ → Download diagnostics** shows each connection, and for each station every train on the board with its stop list and whether it is shown. Attach it when reporting a missing train.

## How it works

The mittog.dk web app opens a WebSocket per board:

- S-tog: `wss://api.mittog.dk/api/ws/stog/departure/<CODE>/`
- Tog: `wss://api.mittog.dk/api/ws/departure/<CODE>/dinstation/`

The server pushes a full snapshot of the board every 10–60 seconds. The integration keeps one connection per board. It hides the same trains mittog.dk hides: freight, technical stops, set-down-only stops, and trains that terminate at the station. It then applies each station's direction and filters. The station list comes from the mittog.dk web app.

## Development

```bash
pip install -r requirements_test.txt
pytest
```

Tests use real mittog.dk snapshots from `tests/fixtures`.

## License

MIT
