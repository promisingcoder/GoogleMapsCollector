"""
Google Maps PB Parameter Decoder

Decodes the pb (protobuf-like) parameter format used in Google Maps URLs.

Format: !{field_number}{type}{value}

Types:
  s = string
  i = integer
  d = double (decimal/float)
  b = boolean (0 or 1)
  m = message (nested structure, followed by field count)
  e = enum
  f = float
"""

import re
from urllib.parse import unquote
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum


class PbFieldType(Enum):
    """Types of pb fields"""
    STRING = 's'
    INTEGER = 'i'
    DOUBLE = 'd'
    BOOLEAN = 'b'
    MESSAGE = 'm'
    ENUM = 'e'
    FLOAT = 'f'

    @classmethod
    def from_char(cls, char: str) -> 'PbFieldType':
        for t in cls:
            if t.value == char:
                return t
        raise ValueError(f"Unknown type character: {char}")

    def get_description(self) -> str:
        descriptions = {
            's': 'string',
            'i': 'integer',
            'd': 'double',
            'b': 'boolean',
            'm': 'message',
            'e': 'enum',
            'f': 'float'
        }
        return descriptions.get(self.value, 'unknown')


@dataclass
class PbField:
    """Represents a single pb field"""
    field_number: int
    field_type: PbFieldType
    value: Any
    raw: str = ""
    children: List['PbField'] = field(default_factory=list)
    description: str = ""

    def to_dict(self) -> Dict:
        """Convert to dictionary representation"""
        result = {
            'field': self.field_number,
            'type': self.field_type.value,
            'type_name': self.field_type.get_description(),
            'value': self.value,
            'raw': self.raw,
        }
        if self.description:
            result['description'] = self.description
        if self.children:
            result['children'] = [child.to_dict() for child in self.children]
        return result


# Known field descriptions for Google Maps
KNOWN_FIELDS = {
    # Root level
    (1, 's'): 'Search Query',
    (4, 'm'): 'Viewport Configuration',
    (7, 'i'): 'Results Count (!7i)',
    (8, 'i'): 'Offset/Start Index (!8i)',
    (10, 'b'): 'Search Enabled',
    (12, 'm'): 'Filters Configuration',
    (19, 'm'): 'Thumbnail Configuration',
    (20, 'm'): 'Image Configuration',
    (22, 'm'): 'Session/Pagination',
    (24, 'm'): 'Place Details Configuration',
    (26, 'm'): 'Marker Size',
    (30, 'm'): 'Viewport Regions',
    (34, 'm'): 'Display Options',
    (37, 'm'): 'Response Format',
    (42, 'b'): 'Flag 42',
    (49, 'm'): 'Search Options',
    (50, 'm'): 'Result Format',
    (61, 'b'): 'Flag 61',
    (67, 'm'): 'Additional Options',
    (69, 'i'): 'Unknown Int 69',

    # Inside !4m (Viewport)
    (1, 'm', 4): 'Coordinates',
    (3, 'm', 4): 'Screen Size',
    (4, 'f', 4): 'Zoom Level',

    # Inside !1m (Coordinates under !4m)
    (1, 'd'): 'Viewport Distance (meters)',
    (2, 'd'): 'Center Longitude',
    (3, 'd'): 'Center Latitude',

    # Inside !3m (Screen Size under !4m)
    (1, 'i'): 'Screen Width (px)',
    (2, 'i'): 'Screen Height (px)',

    # Inside !6m (Search Config under !12m)
    (49, 'b'): 'Include Business Info',
    (66, 'b'): 'Include Hours',
    (74, 'i'): 'Max Search Radius (meters)',
    (85, 'b'): 'Include Website',
    (91, 'b'): 'Include Phone',
    (114, 'b'): 'Include Address',

    # Inside !22m (Session/Pagination)
    (1, 's'): 'Session Token',
    (7, 'e'): 'Token Type',
    (15, 'i'): 'Pagination Cursor/Offset',
}


class PbDecoder:
    """Decoder for Google Maps pb parameter format"""

    def __init__(self):
        self.field_pattern = re.compile(r'!(\d+)([smidbef])(.+?)(?=!|$)')
        self.message_pattern = re.compile(r'!(\d+)m(\d+)')

    def decode(self, pb_string: str) -> List[PbField]:
        """
        Decode a pb parameter string into a list of fields.

        Args:
            pb_string: The pb parameter value (URL decoded)

        Returns:
            List of PbField objects representing the decoded structure
        """
        # URL decode if needed
        if '%21' in pb_string or '%2' in pb_string:
            pb_string = unquote(pb_string)

        return self._parse_fields(pb_string)

    def _parse_fields(self, pb_string: str, depth: int = 0) -> List[PbField]:
        """Parse pb string into list of fields"""
        fields = []
        pos = 0

        while pos < len(pb_string):
            if pb_string[pos] != '!':
                pos += 1
                continue

            # Try to match a field
            remaining = pb_string[pos:]

            # Check if it's a message field (e.g., !4m8)
            msg_match = self.message_pattern.match(remaining)
            if msg_match:
                field_num = int(msg_match.group(1))
                field_count = int(msg_match.group(2))

                # Find the content of this message
                msg_start = pos + len(msg_match.group(0))
                msg_content, msg_end = self._extract_message_content(pb_string, msg_start, field_count)

                # Recursively parse children
                children = self._parse_fields(msg_content, depth + 1)

                field_obj = PbField(
                    field_number=field_num,
                    field_type=PbFieldType.MESSAGE,
                    value=field_count,
                    raw=f"!{field_num}m{field_count}",
                    children=children,
                    description=self._get_description(field_num, 'm')
                )
                fields.append(field_obj)
                pos = msg_end
                continue

            # Try to match regular field
            field_match = re.match(r'!(\d+)([sidebf])([^!]*)', remaining)
            if field_match:
                field_num = int(field_match.group(1))
                field_type_char = field_match.group(2)
                field_value_str = field_match.group(3)

                try:
                    field_type = PbFieldType.from_char(field_type_char)
                    value = self._parse_value(field_type, field_value_str)

                    field_obj = PbField(
                        field_number=field_num,
                        field_type=field_type,
                        value=value,
                        raw=field_match.group(0),
                        description=self._get_description(field_num, field_type_char)
                    )
                    fields.append(field_obj)
                except ValueError:
                    pass

                pos += len(field_match.group(0))
                continue

            pos += 1

        return fields

    def _extract_message_content(self, pb_string: str, start: int, expected_fields: int) -> Tuple[str, int]:
        """
        Extract the content of a message field.

        In Google's pb format, !Nm means N total fields INCLUDING all nested fields.
        So !4m8 contains 8 fields total, counting recursively.
        When we encounter a nested message, we recursively consume its content.
        """
        content = []
        pos = start
        total_field_count = 0

        while pos < len(pb_string) and total_field_count < expected_fields:
            if pb_string[pos] != '!':
                pos += 1
                continue

            remaining = pb_string[pos:]

            # Check for message start
            msg_match = self.message_pattern.match(remaining)
            if msg_match:
                nested_count = int(msg_match.group(2))
                # This message counts as 1, plus all its nested fields
                total_field_count += 1 + nested_count
                if total_field_count > expected_fields:
                    # This message would exceed our count, don't include it
                    total_field_count -= 1 + nested_count
                    break
                # Recursively consume the nested message content
                msg_header = msg_match.group(0)
                nested_content, new_pos = self._extract_message_content(
                    pb_string, pos + len(msg_header), nested_count
                )
                content.append(msg_header + nested_content)
                pos = new_pos
                continue

            # Check for regular field
            field_match = re.match(r'!(\d+)([sidebf])([^!]*)', remaining)
            if field_match:
                total_field_count += 1
                if total_field_count > expected_fields:
                    break
                content.append(field_match.group(0))
                pos += len(field_match.group(0))
                continue

            pos += 1

        return ''.join(content), pos

    def _parse_value(self, field_type: PbFieldType, value_str: str) -> Any:
        """Parse a value string based on its type"""
        if field_type == PbFieldType.STRING:
            return value_str
        elif field_type == PbFieldType.INTEGER:
            return int(value_str) if value_str else 0
        elif field_type == PbFieldType.DOUBLE:
            return float(value_str) if value_str else 0.0
        elif field_type == PbFieldType.FLOAT:
            return float(value_str) if value_str else 0.0
        elif field_type == PbFieldType.BOOLEAN:
            return value_str == '1'
        elif field_type == PbFieldType.ENUM:
            return int(value_str) if value_str else 0
        else:
            return value_str

    def _get_description(self, field_num: int, type_char: str) -> str:
        """Get description for a known field"""
        key = (field_num, type_char)
        return KNOWN_FIELDS.get(key, '')

    def decode_to_dict(self, pb_string: str) -> List[Dict]:
        """Decode pb string and return as list of dictionaries"""
        fields = self.decode(pb_string)
        return [f.to_dict() for f in fields]

    def decode_to_flat(self, pb_string: str) -> List[Dict]:
        """Decode pb string and return as flat list with path notation"""
        fields = self.decode(pb_string)
        flat = []
        self._flatten_fields(fields, '', flat)
        return flat

    def _flatten_fields(self, fields: List[PbField], prefix: str, result: List[Dict]):
        """Flatten nested fields with path notation"""
        for f in fields:
            path = f"{prefix}!{f.field_number}{f.field_type.value}"
            if f.field_type == PbFieldType.MESSAGE:
                path += str(f.value)

            entry = {
                'path': path,
                'field': f.field_number,
                'type': f.field_type.value,
                'type_name': f.field_type.get_description(),
                'value': f.value if f.field_type != PbFieldType.MESSAGE else f"({f.value} fields)",
                'raw': f.raw,
            }
            if f.description:
                entry['description'] = f.description

            result.append(entry)

            if f.children:
                self._flatten_fields(f.children, path, result)


def decode_pb(pb_string: str) -> List[PbField]:
    """
    Convenience function to decode a pb parameter string.

    Args:
        pb_string: The pb parameter value

    Returns:
        List of PbField objects
    """
    decoder = PbDecoder()
    return decoder.decode(pb_string)


def decode_pb_to_dict(pb_string: str) -> List[Dict]:
    """Decode pb string to list of dictionaries"""
    decoder = PbDecoder()
    return decoder.decode_to_dict(pb_string)


def decode_pb_to_flat(pb_string: str) -> List[Dict]:
    """Decode pb string to flat list with paths"""
    decoder = PbDecoder()
    return decoder.decode_to_flat(pb_string)


# Test
if __name__ == "__main__":
    test_pb = "!1stest+query!4m8!1m3!1d50000!2d-74.03!3d40.73!3m2!1i1024!2i768!4f13.1!7i20!8i0"

    print("=== Hierarchical ===")
    fields = decode_pb(test_pb)
    for f in fields:
        print(f"!{f.field_number}{f.field_type.value}: {f.value}")
        for child in f.children:
            print(f"  !{child.field_number}{child.field_type.value}: {child.value}")

    print("\n=== Flat ===")
    flat = decode_pb_to_flat(test_pb)
    for entry in flat:
        print(f"{entry['path']}: {entry['value']}")
