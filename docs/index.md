# Selectarr

Smart Collections in [Jellyfin](https://jellyfin.org/) - Select media with SQL-like queries.

Designed to replace Plex's smart playlists feature. Create collections like '90s Simpsons' or 'Toy Story' without needing to add every TV series, episode, or movie one-by-one. Create dynamic collections, such as including only unplayed media.

## Supported Query Conditions

- `Played = false` (boolean) - filters based on whether media has been watched
- `SeriesName LIKE "The Office"` (string) - matches TV Show/Series name containing the specified text
- `ProductionYear > 1950` (integer) - filters by production year (supports >, <, =, >=, <=)

### Boolean Logic

- `AND` - combine multiple conditions
- Examples:
  - `WHERE Played = false AND SeriesName LIKE "Taskmaster"`
  - `WHERE SeriesName LIKE "Simpsons" AND ProductionYear > 1989 AND ProductionYear < 2000`

Look at [config.yml](https://github.com/jeffwhite530/Selectarr/blob/main/config.yml) for more examples.
