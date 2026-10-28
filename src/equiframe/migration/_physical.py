"""Compatibility aliases for the shared captured-table implementation.

Physical table verification belongs to captured evidence, not migration. The
aliases retain internal consumer identity while formats and behavior stay intact.
"""

from equiframe._physical import physical_size as physical_size
from equiframe._physical import verify_table_metadata as verify_table_metadata
