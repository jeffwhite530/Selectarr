"""
SQL-like query parsing and condition matching.
"""

import logging
import typing

import pyparsing

logger = logging.getLogger(__name__)


def parse_query_conditions(query: str) -> typing.Dict[str, typing.Any]:
  """Parse WHERE clause conditions using pyparsing.

  Supports AND, OR operators and parentheses for grouping.

  Args:
    query: SQL-like query string

  Returns:
    Nested condition tree structure
  """
  # Basic elements
  field = pyparsing.Word(pyparsing.alphas, pyparsing.alphanums + "_")
  operator = pyparsing.one_of("= != > < >= <= LIKE", caseless=True)
  quoted_string = pyparsing.QuotedString('"')
  number = pyparsing.Regex(r'\d+')
  boolean = pyparsing.one_of("true false", caseless=True)
  value = quoted_string | number | boolean

  # Single condition
  condition = pyparsing.Group(field + operator + value)

  # Use infixNotation to handle AND/OR with proper precedence
  # AND has higher precedence than OR (standard SQL behavior)
  expr = pyparsing.infixNotation(
    condition,
    [
      (pyparsing.CaselessKeyword("AND"), 2, pyparsing.opAssoc.LEFT),
      (pyparsing.CaselessKeyword("OR"), 2, pyparsing.opAssoc.LEFT),
    ]
  )

  # Parse after WHERE
  where_parser = pyparsing.CaselessKeyword("WHERE") + expr

  try:
    parsed = where_parser.parseString(query)
    # Convert parsed result to tree structure (skip WHERE keyword)
    return _build_tree(parsed[1])
  except pyparsing.ParseException as e:
    logger.error(f"Failed to parse query: {e}")
    return {'type': 'AND', 'children': []}


def _build_tree(parsed: typing.Any) -> typing.Dict[str, typing.Any]:
  """Convert pyparsing result to condition tree.

  Args:
    parsed: Pyparsing parse result

  Returns:
    Condition tree structure
  """
  if isinstance(parsed, pyparsing.ParseResults):
    # Check if this is a chained operator expression: [cond, OP, cond, OP, cond, ...]
    # Operators are at odd indices (1, 3, 5, ...), conditions at even indices
    if len(parsed) >= 3 and len(parsed) % 2 == 1:
      # Check if odd positions are all the same operator
      operators = [parsed[i] for i in range(1, len(parsed), 2)]
      if all(isinstance(op, str) and op.upper() in ('AND', 'OR') for op in operators):
        first_op = operators[0].upper()
        if all(op.upper() == first_op for op in operators):
          # All operators are the same - build a flat tree
          children = []
          for i in range(0, len(parsed), 2):
            child = _build_tree(parsed[i])
            # Flatten nested same-type operations
            if child.get('type') == first_op:
              children.extend(child['children'])
            else:
              children.append(child)
          return {'type': first_op, 'children': children}

    # Check for leaf condition: [field, operator, value]
    if len(parsed) == 3 and not isinstance(parsed[1], str):
      pass  # Not a condition, fall through
    elif len(parsed) == 3:
      first_elem = parsed[0]
      if isinstance(first_elem, str) and parsed[1].upper() not in ('AND', 'OR'):
        return {
          'type': 'condition',
          'field': parsed[0],
          'operator': parsed[1],
          'value': parsed[2]
        }

    # Unwrap single-element list
    if len(parsed) == 1:
      return _build_tree(parsed[0])

  # Fallback for single condition (non-ParseResults)
  if hasattr(parsed, '__iter__') and len(parsed) == 3:
    first_elem = parsed[0] if hasattr(parsed, '__getitem__') else list(parsed)[0]
    if isinstance(first_elem, str):
      return {
        'type': 'condition',
        'field': parsed[0],
        'operator': parsed[1],
        'value': parsed[2]
      }

  logger.warning(f"Unexpected parse result: {parsed}")
  return {'type': 'AND', 'children': []}


def matches_all_conditions(item: typing.Dict[str, typing.Any], conditions: typing.Dict[str, typing.Any]) -> bool:
  """Check if item matches the condition tree.

  Args:
    item: Media item to test
    conditions: Condition tree structure

  Returns:
    True if item matches conditions
  """
  cond_type = conditions.get('type')

  if cond_type == 'condition':
    return _matches_condition(item, conditions)
  elif cond_type == 'AND':
    children = conditions.get('children', [])
    if not children:
      return True
    return all(matches_all_conditions(item, child) for child in children)
  elif cond_type == 'OR':
    children = conditions.get('children', [])
    if not children:
      return True
    return any(matches_all_conditions(item, child) for child in children)

  return True


def _matches_condition(item: typing.Dict[str, typing.Any], condition: typing.Dict[str, typing.Any]) -> bool:
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

  # Get field value from item - UserData fields
  if field in ('played', 'playcount', 'playbackpositionticks'):
    user_data = item.get('UserData', {})
    if field == 'played':
      item_value = user_data.get('Played', False)
      value = value.lower() == 'true'
    elif field == 'playcount':
      item_value = user_data.get('PlayCount', 0)
      value = int(value)
    elif field == 'playbackpositionticks':
      item_value = user_data.get('PlaybackPositionTicks', 0)
      value = int(value)
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
    result = str(value) in str(item_value)
    if field == 'seriesname' and not result:
      logger.debug(f"LIKE miss: '{value}' not in '{item_value}'")
    return result

  return False
