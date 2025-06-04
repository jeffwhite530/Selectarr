# Selectarr

Smart Collections in [Jellyfin](https://jellyfin.org/) - Select media with SQL-like queries.

Designed to replicate the smart playlists feature of [Plex](https://www.plex.tv/). With Selectarr, create collections like '90s Simpsons' or 'Toy Story' without needing to add every TV series, episode, or movie one-by-one. Create dynamic collections such as 'Unplayed Movies'.

Documentation can be found here: [https://jeffwhite530.github.io/Selectarr/](https://jeffwhite530.github.io/Selectarr/)

## Setup

1. Get an API key from Jellyfin: Settings --> Dashboard --> API Keys
1. Create a `config.yml` file with your Jellyfin server details and collection definitions.
1. Run Selectarr! Either use the provided container image, build your own, or just launch run.py.

## Configuration

Selectarr uses a configuration file, written in YAML. Here is a minimal example:

```yaml
---
jellyfin_server:
  url: http://jellyfin.yourdomain
  user: yourusername

collections:
  TV Shows - Unplayed:
    query: WHERE Played = false
    from: TV Shows
```

### Supported Query Conditions

- `Played = false` (boolean) - filters based on whether media has been watched
- `SeriesName LIKE "The Office"` (string) - matches TV Show/Series name containing the specified text
- `ProductionYear > 1950` (integer) - filters by production year (supports >, <, =, >=, <=)

### Boolean Logic

- `AND` - combine multiple conditions

### Examples

- `WHERE Played = false AND SeriesName LIKE "Taskmaster"`
- `WHERE SeriesName LIKE "Simpsons" AND ProductionYear > 1989 AND ProductionYear < 2000`

Look at [config_example.yml](config_example.yml) for a full example.

## Using the Container Image

Selectarr is available as a container image. Create your config.yml and API key then run it with:

```bash
docker run -e JELLYFIN_API_KEY=your_api_key_here -v $(pwd)/config.yml:/app/config.yml jeffwhite530/selectarr:latest
```

Append options like --debug or --dry-run:

```bash
docker run -e JELLYFIN_API_KEY=your_api_key_here -v $(pwd)/config.yml:/app/config.yml jeffwhite530/selectarr:latest --help
```

## Building From Source

Create a Python virtual environment, activate it, update pip, and install requirements:

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Set environment variable and run:

```bash
export JELLYFIN_API_KEY=your_api_key_here
python run.py --help
```

Append options like --debug or --dry-run:

```bash
python run.py --help
```

## Alternative Build: Container Image

Build image:

```bash
docker build -t selectarr .
```

Run container:

```bash
docker run -e JELLYFIN_API_KEY=your_api_key_here -v $(pwd)/config.yml:/app/config.yml selectarr
```

Append options like --debug or --dry-run:

```bash
docker run -e JELLYFIN_API_KEY=your_api_key_here -v $(pwd)/config.yml:/app/config.yml selectarr --help
```
