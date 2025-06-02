"""
Collection processing and synchronization logic.
"""

import logging
import typing

import requests
import selectarr.jellyfin_client

logger = logging.getLogger(__name__)


def process_collections(session: requests.Session, base_url: str, user_id: str, collections_config: typing.Dict[str, typing.Any], dry_run: bool) -> bool:
  """Process all collections from configuration.
  
  Args:
    session: HTTP session with retry strategy
    base_url: Jellyfin server URL
    user_id: User ID
    collections_config: Collections configuration dictionary
    dry_run: Whether to simulate changes without making them
    
  Returns:
    True if successful, False if errors occurred
  """
  existing_collections = selectarr.jellyfin_client.get_existing_collections(session, base_url, user_id)
  existing_names = {col['Name'] for col in existing_collections}
  logger.debug(f"Existing collection names: {existing_names}")
  
  logger.info(f"Found {len(collections_config)} collection(s) to process")
  
  # Track if any errors occurred
  has_errors = False
  
  for collection_name, collection_config in collections_config.items():
    logger.info(f"Processing collection: {collection_name}")
    
    # Create collection if it doesn't exist
    collection_id = None
    if collection_name not in existing_names:
      if dry_run:
        logger.info(f"[DRY RUN] Would create new collection: {collection_name}")
        # Skip the rest since we can't process without a real collection
        continue
      
      logger.info(f"Creating new collection: {collection_name}")
      try:
        result = selectarr.jellyfin_client.create_collection(session, base_url, collection_name, [])
        collection_id = result.get('Id')
        logger.info(f"Created collection: {collection_name}")
        # Add to existing names to avoid recreating in future iterations
        existing_names.add(collection_name)
      except Exception as e:  # pylint: disable=broad-exception-caught
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
        items = selectarr.jellyfin_client.get_media_items(session, base_url, user_id, library_name, query)
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
        current_item_list, current_item_names = selectarr.jellyfin_client.get_collection_items(session, base_url, collection_id, user_id)
        current_item_ids = set(current_item_list)
        logger.info(f"Collection currently contains {len(current_item_ids)} items")
        
        items_to_add = desired_item_ids - current_item_ids
        items_to_remove = current_item_ids - desired_item_ids
        
        # Add missing items
        if items_to_add:
          if dry_run:
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
            selectarr.jellyfin_client.add_to_collection(session, base_url, collection_id, list(items_to_add))
        else:
          logger.info("No new items to add")
          
        # Remove items that shouldn't be there
        if items_to_remove:
          if dry_run:
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
            selectarr.jellyfin_client.remove_from_collection(session, base_url, collection_id, list(items_to_remove))
        else:
          logger.info("No items to remove")
          
      except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error(f"Failed to sync collection items: {e}")
        has_errors = True
        continue
    else:
      logger.warning(f"Missing query or library for collection '{collection_name}'")
  
  return not has_errors
