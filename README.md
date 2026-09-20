<div align="center">

<img src="assets/logo.png" alt="Stremhu debrid sidecar" width="320">

# Stremhu debrid sidecar

A Stremhu debrid sidecar figyeli, mit játszottál le [Stremhu](https://github.com/s4pp1/Stremhu-source)-val, és feltölti
a debrid szolgáltatódhoz, hogy az legközelebb már cache-ből indulhasson. Emellett akár megoszthatod a debrid könyvtárat tartalmát a közösséggel is.

[![ci](https://github.com/peterdeme/Stremhu-debrid-sidecar/actions/workflows/ci.yaml/badge.svg)](https://github.com/peterdeme/Stremhu-debrid-sidecar/actions/workflows/ci.yaml)
[![lint](https://github.com/peterdeme/Stremhu-debrid-sidecar/actions/workflows/lint.yaml/badge.svg)](https://github.com/peterdeme/Stremhu-debrid-sidecar/actions/workflows/lint.yaml)
[![Python](https://img.shields.io/badge/Python-3.14+-3776AB?logo=python&logoColor=white)](https://www.python.org)
[![License: AGPL-3.0](https://img.shields.io/badge/license-AGPL--3.0-blue)](LICENSE)

</div>

---

## ✨ Mit csinál

- **Debrid szolgáltatóhoz feltöltés.** A Stremhuval lejátszott torrentek felkerülnek a debrid fiókodba, így azt mások is tudják hasznosítani.
- **Season pack-eknél a legjobb.** Az első epizódot még Stremhuból nézed, a másodikat már akár cache-ből is.
- **Közösségi megosztás (opcionális).** A debrid fiókodban cache-elt hash-eket közzéteszi a Debrid Media Managerben, hogy másoknak is elérhetővé váljanak.

## 🔄 Debrid szinkronizációs job

```mermaid
flowchart LR
    subgraph Stremhu
        db[("SQLite")]
    end

    subgraph sidecar["Stremhu debrid sidecar"]
        job["sync job"]
    end

    debrid["Debrid szolgáltató"]

    db -- "olvasás" --> job
    job -- ".torrent feltöltés" --> debrid
```

A Stremhu debrid sidecar bizonyos időközönként beleolvas a Stremhu SQLite adatbázisába, és feltölti az ott talált torrenteket a debrid szolgáltatódhoz.

> Be lehet állítani, hogy milyen feltételek teljesülésekor történjen meg a feltöltés. Például ha csak pár másodpercet játszottál egy torrentből, akkor a feltöltés elkerülhető.

## 🌍 Közösség felé szinkronizáló job (opcionális)

```mermaid
flowchart LR
    debrid["Debrid szolgáltató"]

    subgraph sidecar["Stremhu debrid sidecar"]
        job["publish job"]
    end

    debrid -- "könyvtár lekérdezés" --> job
    job -- "új hash-ek" --> dmm
```

A [`dmm` adatbázist](https://github.com/debridmediamanager/hashlists) többek közt a [Zilean](https://github.com/iPromKnight/zilean/blob/8bfd20d49deda5e263a06476b47176d2a876a200/src/Zilean.Scraper/Features/Ingestion/Dmm/DmmFileDownloader.cs), a [Comet](https://github.com/g0ldyy/comet/blob/f56677f05ed9a158f9a0338ad2f44d8efde35969/comet/services/dmm_ingester.py), a [StremThru Torz](https://github.com/MunifTanjim/stremthru/blob/82e9d782c0e134f37f87fb6267426d28e714128f/internal/worker/sync_dmm_hashlist.go) és a [MediaFusion](https://github.com/mhdzumair/MediaFusion/blob/f48113e53daf66d62afec377907dfef0dce32b84/backend/src/jobs/handlers/dmm_hashlist.rs) is olvassa, így mindenki számára elérhetővé válik.

> [!NOTE]
> Egy hash listában a fájlnév az egyetlen metaadat, amiből a scraperek dolgozni tudnak. Ha a
> név hiányos, például nincs benne az évszám, a hash ugyan bekerül az adatbázisba, de rossz filmhez vagy sorozathoz
> társul, és a keresőkben nem jön elő.

## 🏁 Elindítás

```yaml
services:
  stremhu-source:
    image: s4pp1/stremhu-source:latest
    ports:
      - "6881:6881"
    volumes:
      - ./stremhu-data:/app/data

  stremhu-debrid-sidecar:
    image: ghcr.io/peterdeme/stremhu-debrid-sidecar:latest
    ports:
      - "127.0.0.1:8000:8000"
    volumes:
      - ./sidecar-data:/data
      - ./stremhu-data/system/database:/stremhu/system/database
      - ./stremhu-data/downloads:/stremhu/downloads:ro
```

> Az adatbázis könyvtára nem lehet csak olvasható (`:ro`): az SQLite a [write-ahead napló](https://www.sqlite.org/wal.html) (WAL) olvasásához létrehoz egy `-shm` fájlt a db mellé. Magába az adatbázisba nem írunk.

Ezután nyisd meg a `http://localhost:8000` címet, és add meg a debrid API kulcsodat. A belépési
jelszót az első indításkor generáljuk és kiírjuk a logba (`docker compose logs`), vagy megadhatod
az `ADMIN_PASSWORD` környezeti változóval is.

> [!WARNING]
> A port szándékosan a `127.0.0.1` címre van kötve: a webes felület csak a beállításokhoz kell,
> az ütemezett feladatok attól függetlenül futnak, hogy eléri-e valaki. Ne tedd ki az internetre.
> Ha végeztél a beállítással, a `ports` blokk akár teljesen el is hagyható, a sidecar ugyanúgy
> működik tovább.


## 🛠 Fejlesztés

```sh
python -m venv .venv && .venv/bin/pip install -e .
.venv/bin/uvicorn app.main:app --reload
```

## ⚖️ Jogi nyilatkozat

Ez az eszköz nem keres, nem indexel és nem szolgáltat tartalmat. Kizárólag azokat a
torrenteket mozgatja a saját debrid fiókodba, amelyeket a Stremhuval már lejátszottál,
a saját gépeden, a saját fiókjaiddal, a saját trackereiddel.

Azért, hogy mit töltesz le és mit teszel közzé, te felelsz. A szerzői jogi szabályok
országonként eltérnek, a privát trackerek szabályzata pedig külön köt. **Szerzői joggal védett
tartalom jogosulatlan letöltését vagy terjesztését a projekt nem támogatja.**

---

<div align="center">
<a href="LICENSE">AGPL-3.0 licenc</a>. A projekt nem áll kapcsolatban semmilyen trackerrel, a Stremhuval, debrid szolgáltatókkal és a Debrid Media Managerrel sem.
</div>
