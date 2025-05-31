# Selectarr

Smart Collections in [Jellyfin](https://jellyfin.org/) - Select media with SQL-like queries.

Designed to replicate the smart playlists feature of [Plex](https://www.plex.tv/). With Selectarr, create collections like '90s Simpsons' or 'Toy Story' without needing to add every TV series, episode, or movie one-by-one. Create dynamic collections, such as including only unplayed media.

Documentation can be found here: [https://jeffwhite530.github.io/Selectarr/](https://jeffwhite530.github.io/Selectarr/)

## Supported Query Conditions

- `Played = false` (boolean) - filters based on whether media has been watched
- `SeriesName LIKE "The Office"` (string) - matches TV Show/Series name containing the specified text
- `ProductionYear > 1950` (integer) - filters by production year (supports >, <, =, >=, <=)

### Boolean Logic

- `AND` - combine multiple conditions
- Examples:
  - `WHERE Played = false AND SeriesName LIKE "Taskmaster"`
  - `WHERE SeriesName LIKE "Simpsons" AND ProductionYear > 1989 AND ProductionYear < 2000`

Look at [config.yml](config.yml) for more examples.

## Installation

Create a Python virtual environment, activate it, update pip, and install requirements:

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## Setup

1. Get API key from Jellyfin: Settings --> Dashboard --> API Keys
1. Create a `config.yml` file with your Jellyfin server details and collection definitions

## Usage

Set environment variable and run:

```bash
export JELLYFIN_API_KEY=your_api_key_here
python run.py --help
```

For debug output:

```bash
python run.py --debug
```

## Alternative Setup: Docker

Build image:

```bash
docker build -t selectarr .
```

Run container:

```bash
docker run -e JELLYFIN_API_KEY=your_api_key_here -v $(pwd)/config.yml:/app/config.yml selectarr
```

For debug output:

```bash
docker run -e JELLYFIN_API_KEY=your_api_key_here -v $(pwd)/config.yml:/app/config.yml selectarr --debug
```
