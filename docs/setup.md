# Setup

1. Get an API key from Jellyfin: Settings --> Dashboard --> API Keys
1. Create a `config.yml` file with your Jellyfin server details and collection definitions

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

Look at [config_example.yml](https://github.com/jeffwhite530/Selectarr/blob/main/config_example.yml) for a full example.

## Using the Container Image

Selectarr is available as a container image. Create your config.yml and API key then run it with:

```bash
docker run -e JELLYFIN_API_KEY=your_api_key_here -v $(pwd)/config.yml:/app/config.yml jeffwhite530/selectarr:latest
```

Append options like --debug or --dry-run:

```bash
docker run -e JELLYFIN_API_KEY=your_api_key_here -v $(pwd)/config.yml:/app/config.yml jeffwhite530/selectarr:latest --help
```
