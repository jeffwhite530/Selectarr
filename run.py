#!/usr/bin/env python3
"""
Selectarr - Smart Collections in Jellyfin - Select media with SQL-like queries.
"""

import argparse
import logging
import os
import re
import sys
import typing

import requests
import urllib3.util.retry
import yaml
import pyparsing

logger = logging.getLogger(__name__)




def get_existing_collections(session: requests.Session, base_url: str, user_id: str) -> typing.List[typing.Dict[str, typing.Any]]:
  """Get all existing collections for a user.
  
  Args:
    session: HTTP session with retry strategy
    base_url: Jellyfin server URL
    user_id: User ID to get collections for
    
  Returns:
    List of collection dictionaries
  """
  # First, get the Collections library ID
  try:
    collections_library_id = get_library_id(session, base_url, user_id, "Collections")
    logger.debug(f"Found Collections library with ID: {collections_library_id}")
  except ValueError:
    logger.warning("Collections library not found - no existing collections")
    return []
  
  # Now get the actual collections within the Collections library
  params = {
    'ParentId': collections_library_id,
    'IncludeItemTypes': 'BoxSet',
    'recursive': 'true'
  }
  url = f"{base_url}/Users/{user_id}/Items"
  
  logger.debug(f"Getting existing collections from: {url}")
  logger.debug(f"Request params: {params}")
  
  response = session.get(url, params=params, timeout=10)
  response.raise_for_status()
  
  result = response.json()
  items = result.get('Items', [])
  
  logger.debug(f"API response contains {len(items)} collections")
  for item in items:
    logger.debug(f"Collection found: '{item.get('Name', 'Unknown')}' (ID: {item.get('Id', 'Unknown')})")
  
  return items


def parse_query_conditions(query: str) -> typing.List[typing.Dict[str, typing.Any]]:
  """Parse WHERE clause conditions using pyparsing.
  
  Args:
    query: SQL-like query string
    
  Returns:
    List of condition dictionaries
  """
  # Simple parser for basic conditions
  field = pyparsing.Word(pyparsing.alphas, pyparsing.alphanums + "_")
  operator = pyparsing.oneOf("= != > < >= <= LIKE", caseless=True)
  quoted_string = pyparsing.QuotedString('"')
  number = pyparsing.Regex(r'\d+')
  boolean = pyparsing.oneOf("true false", caseless=True)
  value = quoted_string | number | boolean
  
  # Single condition
  condition = pyparsing.Group(field + operator + value)
  
  # Multiple conditions with AND (simplified - just AND for now)
  conditions_list = condition + pyparsing.ZeroOrMore(pyparsing.CaselessKeyword("AND") + condition)
  
  # Parse after WHERE
  where_parser = pyparsing.CaselessKeyword("WHERE") + conditions_list
  
  try:
    parsed = where_parser.parseString(query)
    # Extract conditions (skip WHERE keyword)
    conditions = []
    for item in parsed[1:]:
      if isinstance(item, pyparsing.ParseResults) and len(item) == 3:
        conditions.append({
          'field': item[0],
          'operator': item[1], 
          'value': item[2]
        })
    return conditions
  except pyparsing.ParseException as e:
    logger.error(f"Failed to parse query: {e}")
    return []


def matches_all_conditions(item: typing.Dict[str, typing.Any], conditions: typing.List[typing.Dict[str, typing.Any]]) -> bool:
  """Check if item matches all conditions (AND logic).
  
  Args:
    item: Media item to test
    conditions: List of condition dictionaries
    
  Returns:
    True if item matches all conditions
  """
  for condition in conditions:
    if not matches_condition(item, condition):
      return False
  return True


def matches_condition(item: typing.Dict[str, typing.Any], condition: typing.Dict[str, typing.Any]) -> bool:
  """Check if item matches a single condition.
  
  Args:
    item: Media item to test  
    condition: Single condition dictionary
    
  Returns:
    True if condition matches
  """
  field = condition['field'].lower()
  operator = condition['operator'].upper()
  value = condition['value']
  
  # Get field value from item
  if field == 'played':
    user_data = item.get('UserData', {})
    played_status = user_data.get('Played', False)
    play_count = user_data.get('PlayCount', 0)
    
    if value.lower() == 'false':
      # For "Played = false", item must be both not played AND never started
      item_value = not played_status and play_count == 0
      value = True  # We want this to be True for the comparison
    elif value.lower() == 'true':
      # For "Played = true", item is either marked played OR has been played at least once
      item_value = played_status or play_count > 0
      value = True  # We want this to be True for the comparison
  elif field == 'seriesname':
    item_value = item.get('SeriesName', '').lower()
    value = value.lower()
  elif field == 'productionyear':
    item_value = item.get('ProductionYear', 0)
    value = int(value)
  else:
    item_value = item.get(field, '')
  
  # Apply operator
  if operator == '=':
    return item_value == value
  elif operator == '!=':
    return item_value != value
  elif operator == '>':
    return item_value > value
  elif operator == '<':
    return item_value < value
  elif operator == '>=':
    return item_value >= value
  elif operator == '<=':
    return item_value <= value
  elif operator == 'LIKE':
    return str(value) in str(item_value)
  
  return False


def get_media_items(session: requests.Session, base_url: str, user_id: str, library_name: str, query: str) -> typing.List[typing.Dict[str, typing.Any]]:
  """Get media items from a library with filters.
  
  Args:
    session: HTTP session with retry strategy
    base_url: Jellyfin server URL
    user_id: User ID for the query
    library_name: Name of the library to search (e.g., "TV Shows")
    query: SQL-like query string (e.g., "WHERE Played = false")
    
  Returns:
    List of media item dictionaries
  """
  # First, get the library ID from the library name
  library_id = get_library_id(session, base_url, user_id, library_name)
  
  # Parse the query to determine filters
  params = {
    'ParentId': library_id,
    'recursive': 'true',
    'enableUserData': 'true',
    'fields': 'BasicSyncInfo,SeriesName,ProductionYear'
  }
  
  # Parse query conditions
  if "Played = false" in query:
    params['isPlayed'] = 'false'
  elif "Played = true" in query:
    params['isPlayed'] = 'true'
  
  # Parse all conditions from query
  conditions = parse_query_conditions(query)
  logger.debug(f"Parsed conditions: {conditions}")
  
  # Determine item type based on library name and what we're looking for
  # For TV Shows, we want episodes not series
  if "Shows" in library_name or "Series" in library_name:
    params['includeItemTypes'] = 'Episode'
    # Exclude virtual/missing episodes
    params['excludeItemTypes'] = 'Virtual'
  elif "Movies" in library_name:
    params['includeItemTypes'] = 'Movie'
  
  logger.info(f"Searching items with params: {params}")
  
  response = session.get(f"{base_url}/Users/{user_id}/Items", 
                         params=params, 
                         timeout=10)
  response.raise_for_status()
  
  result = response.json()
  items = result.get('Items', [])
  
  # Apply all conditions as filters
  original_count = len(items)
  items = [item for item in items if matches_all_conditions(item, conditions)]
  logger.info(f"Filtered {original_count} items to {len(items)} items matching all conditions")
  
  logger.info(f"Found {len(items)} items matching query: {query}")
  
  return items


def get_library_id(session: requests.Session, base_url: str, user_id: str, library_name: str) -> str:
  """Get library ID from library name.
  
  Args:
    session: HTTP session with retry strategy
    base_url: Jellyfin server URL
    user_id: User ID
    library_name: Name of the library
    
  Returns:
    Library ID string
  """
  # Get user views/libraries
  response = session.get(f"{base_url}/Users/{user_id}/Views", 
                         timeout=10)
  response.raise_for_status()
  
  views = response.json().get('Items', [])
  
  for view in views:
    if view['Name'] == library_name:
      return view['Id']
  
  raise ValueError(f"Library '{library_name}' not found")


def get_collection_items(session: requests.Session, base_url: str, collection_id: str, user_id: str) -> typing.Tuple[typing.List[str], typing.Dict[str, str]]:
  """Get all item IDs currently in a collection.
  
  Args:
    session: HTTP session with retry strategy
    base_url: Jellyfin server URL
    collection_id: Collection ID
    user_id: User ID
    
  Returns:
    Tuple of (list of item IDs, dict mapping ID to name)
  """
  params = {
    'ParentId': collection_id,
    'fields': 'Id,Name,SeriesName'
  }
  
  response = session.get(f"{base_url}/Users/{user_id}/Items", 
                         params=params, 
                         timeout=10)
  response.raise_for_status()
  
  result = response.json()
  items = result.get('Items', [])
  
  item_ids = [item['Id'] for item in items]
  id_to_name = {}
  for item in items:
    series_name = item.get('SeriesName', '')
    episode_name = item.get('Name', 'Unknown')
    if series_name:
      display_name = f"{series_name} - {episode_name}"
    else:
      display_name = episode_name
    id_to_name[item['Id']] = display_name
  
  return item_ids, id_to_name


def add_to_collection(session: requests.Session, base_url: str, collection_id: str, item_ids: typing.List[str]) -> None:
  """Add items to a collection.
  
  Args:
    session: HTTP session with retry strategy
    base_url: Jellyfin server URL
    collection_id: Collection ID
    item_ids: List of item IDs to add
  """
  if not item_ids:
    return
  
  # Batch requests to avoid URI too long errors
  # Each item ID is ~32 chars, plus comma, so batch by 50 to be safe
  batch_size = 50
  total_added = 0
  
  for i in range(0, len(item_ids), batch_size):
    batch = item_ids[i:i + batch_size]
    params = {
      'ids': ','.join(batch)
    }
    
    response = session.post(f"{base_url}/Collections/{collection_id}/Items", 
                            params=params, 
                            timeout=10)
    response.raise_for_status()
    total_added += len(batch)
    logger.info(f"Added {len(batch)} batch of items (total: {total_added}/{len(item_ids)})")
  
  logger.info(f"Added {total_added} items to collection")


def remove_from_collection(session: requests.Session, base_url: str, collection_id: str, item_ids: typing.List[str]) -> None:
  """Remove items from a collection.
  
  Args:
    session: HTTP session with retry strategy
    base_url: Jellyfin server URL
    collection_id: Collection ID
    item_ids: List of item IDs to remove
  """
  if not item_ids:
    return
  
  # Batch requests to avoid URI too long errors
  batch_size = 50
  total_removed = 0
  
  for i in range(0, len(item_ids), batch_size):
    batch = item_ids[i:i + batch_size]
    params = {
      'ids': ','.join(batch)
    }
    
    response = session.delete(f"{base_url}/Collections/{collection_id}/Items", 
                              params=params, 
                              timeout=10)
    response.raise_for_status()
    total_removed += len(batch)
    logger.info(f"Removed batch of {len(batch)} items (total: {total_removed}/{len(item_ids)})")
  
  logger.info(f"Removed {total_removed} items from collection")


def create_collection(session: requests.Session, base_url: str, name: str, item_ids: typing.List[str], user_id: str = None) -> typing.Dict[str, typing.Any]:
  """Create a new collection in Jellyfin.
  
  Args:
    session: HTTP session with retry strategy
    base_url: Jellyfin server URL
    name: Name of the collection
    item_ids: List of media item IDs to include
    
  Returns:
    Created collection dictionary
  """
  
  params = {
    'name': name,
    'isLocked': 'false'
  }
  
  # Only include ids if we have items to add
  if item_ids:
    params['ids'] = ','.join(item_ids)
  
  logger.debug(f"Request URL: {base_url}/Collections")
  logger.debug(f"Request params: {params}")
  
  response = session.post(f"{base_url}/Collections", params=params, timeout=10)
  
  if response.status_code != 200:
    logger.error(f"Collection creation failed with status {response.status_code}")
    logger.error(f"Response body: {response.text}")
    logger.error(f"Request params: {params}")
  
  response.raise_for_status()
  
  return response.json()


def main() -> None:
  """Main entry point for Selectarr."""
  parser = argparse.ArgumentParser(
    description="Smart Collections in Jellyfin - Select media with SQL-like queries. Requires JELLYFIN_API_KEY environment variable to be set with your Jellyfin API key.",
    epilog="Get API key from Jellyfin: Settings --> Dashboard --> API Keys"
  )
  parser.add_argument(
    '-d', '--debug',
    action='store_true',
    help='Enable debug logging'
  )
  parser.add_argument(
    '-c', '--config',
    default='config.yml',
    help='Configuration file path (default: config.yml)'
  )
  parser.add_argument(
    '--dry-run',
    action='store_true',
    help='Show what would be done without making changes'
  )
  
  args = parser.parse_args()
  
  # Configure logging
  if args.debug:
    log_level = logging.DEBUG
  else:
    log_level = logging.INFO
  log_format = "%(asctime)s - %(levelname)s - %(message)s"
  logging.basicConfig(stream=sys.stdout, format=log_format, level=log_level)
  
  logger.info("Starting Selectarr")
  
  # Load config
  with open(args.config, 'r', encoding='utf-8') as file:
    config = yaml.safe_load(file)
  logger.debug(f"Loaded config from {args.config}")
  
  base_url = config['main']['jellyfin_url']
  jellyfin_user = config['main']['jellyfin_user']
  api_token = os.getenv('JELLYFIN_API_KEY')
  if not api_token:
    logger.error("JELLYFIN_API_KEY environment variable not set. Get API key from Jellyfin: Settings --> Dashboard --> API Keys")
    sys.exit(1)
  
  # Configure retry strategy for HTTP requests
  retry_strategy = urllib3.util.retry.Retry(
    total=10,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["HEAD", "GET", "POST", "DELETE", "OPTIONS"]
  )
  adapter = requests.adapters.HTTPAdapter(max_retries=retry_strategy)
  
  with requests.Session() as session:
    session.headers.update({
      'Authorization': f'MediaBrowser Client="Selectarr", Device="script", DeviceId="script", Version="1.0.0", Token="{api_token}"',
      'Content-Type': 'application/json',
      'Accept': 'application/json'
    })
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    
    # Get server info
    logger.info("Connecting to Jellyfin server...")
    response = session.get(f"{base_url}/System/Info/Public", timeout=10)
    response.raise_for_status()
    server_info = response.json()
    logger.info(f"Connected to Jellyfin server: {server_info.get('ServerName', 'Unknown')}")
    
    # Get user ID
    response = session.get(f"{base_url}/Users", timeout=10)
    response.raise_for_status()
    users = response.json()
    user_id = None
    for user in users:
      if user['Name'] == jellyfin_user:
        user_id = user['Id']
        break
    if not user_id:
      logger.error(f"User '{jellyfin_user}' not found")
      sys.exit(1)
    logger.debug(f"User ID for '{jellyfin_user}': {user_id}")
    
    existing_collections = get_existing_collections(session, base_url, user_id)
    existing_names = {col['Name'] for col in existing_collections}
    logger.debug(f"Existing collection names: {existing_names}")
    
    collections = config.get('collections', {})
    logger.info(f"Found {len(collections)} collection(s) to process")
    
    # Track if any errors occurred
    has_errors = False
    
    for collection_name, collection_config in collections.items():
      logger.info(f"Processing collection: {collection_name}")
      
      # Create collection if it doesn't exist
      collection_id = None
      if collection_name not in existing_names:
        if args.dry_run:
          logger.info(f"[DRY RUN] Would create new collection: {collection_name}")
          # Skip the rest since we can't process without a real collection
          continue
        else:
          logger.info(f"Creating new collection: {collection_name}")
          try:
            result = create_collection(session, base_url, collection_name, [], user_id)
            collection_id = result.get('Id')
            logger.info(f"Created collection: {collection_name}")
            # Add to existing names to avoid recreating in future iterations
            existing_names.add(collection_name)
          except Exception as e:
            logger.error(f"Failed to create collection '{collection_name}': {e}")
            has_errors = True
            continue
      else:
        logger.info(f"Collection '{collection_name}' already exists")
        # Find the collection ID from existing collections
        for col in existing_collections:
          if col['Name'] == collection_name:
            collection_id = col['Id']
            break
      
      if not collection_id:
        logger.error(f"Could not find collection ID for '{collection_name}'")
        has_errors = True
        continue
        
      # Now search for items to add to the collection
      query = collection_config.get('query', '')
      library_name = collection_config.get('from', collection_config.get('source_collection', ''))
      
      logger.debug(f"Query: {query}")
      logger.debug(f"Library: {library_name}")
      
      if query and library_name:
        try:
          # Get items that should be in the collection based on query
          items = get_media_items(session, base_url, user_id, library_name, query)
          desired_item_ids = {item['Id'] for item in items}
          item_id_to_name = {}
          for item in items:
            series_name = item.get('SeriesName', '')
            episode_name = item.get('Name', 'Unknown')
            if series_name:
              display_name = f"{series_name} - {episode_name}"
            else:
              display_name = episode_name
            item_id_to_name[item['Id']] = display_name
          logger.info(f"Query returned {len(desired_item_ids)} items that should be in collection")
          
          # Get current items in the collection
          current_item_list, current_item_names = get_collection_items(session, base_url, collection_id, user_id)
          current_item_ids = set(current_item_list)
          logger.info(f"Collection currently contains {len(current_item_ids)} items")
          
          items_to_add = desired_item_ids - current_item_ids
          items_to_remove = current_item_ids - desired_item_ids
          
          # Add missing items
          if items_to_add:
            if args.dry_run:
              logger.info(f"[DRY RUN] Would add {len(items_to_add)} new items to collection")
              if items_to_add:
                example_id = next(iter(items_to_add))
                example_name = item_id_to_name.get(example_id, example_id)
                logger.debug(f"[DRY RUN] Example of an item that would be added: {example_name}")
            else:
              logger.info(f"Adding {len(items_to_add)} new items to collection")
              if items_to_add:
                example_id = next(iter(items_to_add))
                example_name = item_id_to_name.get(example_id, example_id)
                logger.debug(f"Example of item added: {example_name}")
              add_to_collection(session, base_url, collection_id, list(items_to_add))
          else:
            logger.info("No new items to add")
            
          # Remove items that shouldn't be there
          if items_to_remove:
            if args.dry_run:
              logger.info(f"[DRY RUN] Would remove {len(items_to_remove)} items from collection")
              if items_to_remove:
                example_id = next(iter(items_to_remove))
                example_name = current_item_names.get(example_id, example_id)
                logger.debug(f"[DRY RUN] Example of an item that would be removed: {example_name}")
            else:
              logger.info(f"Removing {len(items_to_remove)} items from collection")
              if items_to_remove:
                example_id = next(iter(items_to_remove))
                example_name = current_item_names.get(example_id, example_id)
                logger.debug(f"Example of item removed: {example_name}")
              remove_from_collection(session, base_url, collection_id, list(items_to_remove))
          else:
            logger.info("No items to remove")
            
        except Exception as e:
          logger.error(f"Failed to sync collection items: {e}")
          has_errors = True
          continue
      else:
        logger.warning(f"Missing query or library for collection '{collection_name}'")
    
    if has_errors:
      logger.error("Selectarr completed with errors")
      sys.exit(1)
    else:
      logger.info("Selectarr completed successfully")


if __name__ == "__main__":
  main()
