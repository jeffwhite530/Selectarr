#!/usr/bin/env python3
"""
Selectarr - Smart Collections in Jellyfin - Select media with SQL-like queries.
"""

import argparse
import logging
import os
import sys

import requests
import urllib3.util.retry
import yaml

# Add src directory to path for selectarr import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
import selectarr

logger = logging.getLogger(__name__)


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
    
    collections = config.get('collections', {})
    success = selectarr.collection_manager.process_collections(session, base_url, user_id, collections, args.dry_run)
    
    if not success:
      logger.error("Selectarr completed with errors")
      sys.exit(1)
    else:
      logger.info("Selectarr completed successfully")


if __name__ == "__main__":
  main()
