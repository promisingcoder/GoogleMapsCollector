"""
Geographic utilities module.

- grid.py: Grid cell generation for area coverage
- nominatim.py: Boundary fetching from OpenStreetMap Nominatim API
"""

from .grid import GridCell, AreaBoundary, generate_grid, is_in_boundary, calculate_cell_size
from .nominatim import get_area_boundary, get_sub_areas, get_subdivision_areas, SubArea
