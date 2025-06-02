"""
Jellyfin API client functions.
"""

import logging
import typing

import requests
import selectarr.query_parser

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
  conditions = selectarr.query_parser.parse_query_conditions(query)
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
  items = [item for item in items if selectarr.query_parser.matches_all_conditions(item, conditions)]
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


def create_collection(session: requests.Session, base_url: str, name: str, item_ids: typing.List[str]) -> typing.Dict[str, typing.Any]:
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
