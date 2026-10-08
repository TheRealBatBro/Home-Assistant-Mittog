# Changelog

## 1.2.0

- Mittog now has its own icon in Home Assistant (integration page, devices, Add integration).
- Releases: every version is published as a GitHub release, so Home Assistant offers updates under **Settings → Updates** with these notes. No more *Redownload* in HACS.

## 1.1.2

- Sensors no longer flicker to *unknown* just before a departure when the feed briefly drops a train.
- *Must stop at* keeps trains that arrive without a stop list when other trains to the same destination stop at your station. Trains that list their stops and skip your station stay out, e.g. every other evening C train past Vinge.
- Diagnostics list every train on the board, with its stops and whether it is shown.

## 1.1.1

- Adding Mittog again from **Add integration** or **Devices → Add device** now adds the station to your existing Mittog, instead of failing with "single_instance_allowed".

## 1.1.0

- One searchable station list for both boards, e.g. *Vinge (S-tog)* or *København H (Tog)*.
- Directions are picked from the directions trains actually leave in and named after where they go. They include trains that turn back early, e.g. at Svanemøllen.
- Filters (must stop at, lines, tracks) only offer what runs in your direction.

## 1.0.0

- First release: live S-tog and regional departures from mittog.dk, any number of stations.
