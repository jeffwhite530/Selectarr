# Configuration

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

