# Custom Markdown style rules
# Configures specific linting checks and preferences for mdl

all

# Multiple consecutive blank lines
exclude_rule 'MD012'

# Line length
exclude_rule 'MD013'

# Bare URL use
exclude_rule 'MD034'

# Trailing punctuation in headers
rule 'MD026', punctuation: '.,;:!'

# Unordered list indentation
rule 'MD007', indent: 2
