"""
SQL-like query parsing and condition matching.
"""

import logging
import typing

import pyparsing

logger = logging.getLogger(__name__)


def parse_query_conditions(query: str) -> typing.List[typing.Dict[str, typing.Any]]:
  """Parse WHERE clause conditions using pyparsing.
  
  Args:
    query: SQL-like query string
    
  Returns:
    List of condition dictionaries
  """
  # Simple parser for basic conditions
  field = pyparsing.Word(pyparsing.alphas, pyparsing.alphanums + "_")
  operator = pyparsing.one_of("= != > < >= <= LIKE", caseless=True)
  quoted_string = pyparsing.QuotedString('"')
  number = pyparsing.Regex(r'\d+')
  boolean = pyparsing.one_of("true false", caseless=True)
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
    else:
      # Invalid boolean value
      item_value = False
  elif field == 'seriesname':
    item_value = item.get('SeriesName', '').lower()
    value = value.lower()
  elif field == 'productionyear':
    item_value = item.get('ProductionYear', 0)
    value = int(value)
    # Skip items with invalid/missing production years (0 or None)
    if not item_value or item_value == 0:
      return False
  else:
    item_value = item.get(field, '')
  
  # Apply operator
  if operator == '=':
    return item_value == value
  if operator == '!=':
    return item_value != value
  if operator == '>':
    return item_value > value
  if operator == '<':
    return item_value < value
  if operator == '>=':
    return item_value >= value
  if operator == '<=':
    return item_value <= value
  if operator == 'LIKE':
    return str(value) in str(item_value)
  
  return False
