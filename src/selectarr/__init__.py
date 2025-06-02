"""Selectarr package for Jellyfin smart collections."""
import selectarr.collection_manager
import selectarr.jellyfin_client
import selectarr.query_parser

# Expose modules at package level
collection_manager = selectarr.collection_manager
jellyfin_client = selectarr.jellyfin_client
query_parser = selectarr.query_parser
