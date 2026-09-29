# Mittog for Home Assistant

Live train departures from [mittog.dk](https://mittog.dk/da/departures/VNG/stog/) in Home Assistant: S-tog and regional/long-distance trains (DSB, Øresundståg, Lokaltog, Arriva …) for any Danish station.

- **As many stations as you like**, each with its own device and sensors.
- **Directions**: show only trains going your way, e.g. *Vinge → København H*. Add the same station more than once to follow both directions separately.
- Filter by **line / train type** (A, B, C … or Re, IC, ICL …) and by **track**.
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

1. Go to **Settings → Devices & services → + Add integration** and search for **Mittog**.
2. **Board**: choose which departure board you want:
   - **S-tog**: the Copenhagen S-trains (lines A, B, Bx, C, E, F, H).
   - **Tog**: regional and long-distance trains (DSB Re/IC/ICL, Øresundståg, Lokaltog, Arriva, Nordjyske …).

   Big stations such as København H, Østerport, Hellerup, Høje Taastrup and Køge have **both** boards. Pick the one for the train you take. You can add the other one later.
3. **Station**: type the station name or part of it (e.g. `nør`), then press **Submit**.
   - If exactly one station matches, you go straight on.
   - If several match (e.g. *Nørrebro* and *Nørreport*), pick yours from the list.
   - You can also type the **station code** from the mittog.dk address. See [Finding the right station](#finding-the-right-station).
4. **Direction and filters**. The dialog shows how many departures are on the board right now.
   - **Towards (direction)**: pick one or more stations *further along your route*. Only trains that stop at one of them are kept. Leave it empty for both directions. The list only contains stations that trains from here actually call at, and you can type to search it.
   - **Lines / train types** (optional): e.g. `A` and `E`, or `IC` and `ICL`.
   - **Tracks** (optional): e.g. `1` or `1, 2`.
   - **Departures to keep**: how many upcoming departures go into the `departures` attribute (default 10).
   - **Delay threshold**: the *Disruption* sensor turns on when a shown train is at least this many minutes late, or cancelled (default 3).
   - **Hide cancelled departures**: leave cancelled trains out entirely instead of flagging them.
5. **Submit**. You now have a *Mittog* integration with one station, e.g. **Vinge → København H**.

## 3. Add more stations or the other direction

Open **Settings → Devices & services → Mittog** and click **+ Add station** (top right). The steps are the same as above.

Examples:

| You want | Add |
| --- | --- |
| Your morning train into town | S-tog · *Vinge* · towards *København H* |
| The way home | S-tog · *København H* · towards *Vinge* |
| Both directions at your station, separately | *Vinge* towards *København H*, then *Vinge* again towards *Frederikssund* |
| Only IC trains to Odense from Copenhagen | Tog · *København H* · towards *Odense* · lines `IC`, `ICL` |
| Everything from one platform | Tog · *Roskilde* · tracks `1` |

Each station becomes its own device with its own sensors. Adding the exact same station, direction and filters twice is refused.

**Change** a station's direction or filters: click the **✏️ pencil** next to it on the Mittog page.
**Remove** a station: click **⋮** next to it → **Delete**.
**Change the station itself**: delete it and add the new one.

---

## Finding the right station

**By name.** Just type part of the name in the Station step. The list only contains stations that have the board you chose, so if you get *"No station on this board matches"*, try the other board (S-tog vs Tog). For example, Aalborg has no S-tog board.

**By the mittog.dk address.** Open [mittog.dk](https://mittog.dk), find your station and look at the address bar:

```
https://mittog.dk/da/departures/VNG/stog/
                                ^^^ ^^^^
                        station code  board (stog = S-tog, tog = Tog)
```

Type the code (here `VNG`, which is **Vinge**) into the Station field. Codes are not always obvious (Nørreport is `KN`, København H is `KH`, Østerport is `KK`), so the address is handy when a name search gives several similar results.

**Picking the direction.** Choose a station your train passes *after* yours, not the one you are at. Where lines split, choose a station on your branch. For example, from København H towards *Hillerød* gives you the A and E trains to Hillerød, but not the B trains to Farum. When several stations are picked, a train only has to stop at one of them.

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
| **Next departure** (*Næste afgang*) | Time of the next train that is not cancelled (timestamp, delays included) | `line`, `destination`, `track`, `delay`, `minutes`, `cancelled`, `scheduled`, `expected`, `train_number`, `operator`, `color`, `via`, `original_track` (track change), and **`departures`**: the list of upcoming departures, each with the same fields |
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

- **Sensors are *unknown***: no train matches your direction and filters right now (for example at night, or because of a filter that is too tight). Check the unfiltered board on mittog.dk: the device page has a *Visit* link to it.
- **Sensors are *unavailable***: the feed has been silent for 3 minutes. Check *Live connection*. It reconnects by itself, backing off up to 5 minutes.
- **A train you expected is missing**: check the direction. The train must stop at one of your *Towards* stations *after* your station. Trains that terminate at your station are arrivals and are never shown.
- **Debug logging**:

  ```yaml
  logger:
    logs:
      custom_components.mittog: debug
  ```

  **Settings → Devices & services → Mittog → ⋮ → Download diagnostics** shows each connection and what each station keeps.

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
