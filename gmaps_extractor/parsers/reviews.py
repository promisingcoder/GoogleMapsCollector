"""
Reviews Extractor

Extracts reviews from Google Maps place responses.

Reviews are typically found at data[6][52] in place preview responses.
Each review contains:
- Author name
- Rating (1-5)
- Review text
- Date/time
- Profile photo URL
"""

from typing import Dict, List, Any, Optional


def safe_get(obj: Any, *indices, default=None) -> Any:
    """Safely traverse nested structures"""
    try:
        current = obj
        for idx in indices:
            if current is None:
                return default
            if isinstance(current, list) and isinstance(idx, int):
                if idx < len(current):
                    current = current[idx]
                else:
                    return default
            elif isinstance(current, dict):
                current = current.get(idx, default)
            else:
                return default
        return current
    except (IndexError, KeyError, TypeError):
        return default


def find_reviews_in_data(data: Any, depth: int = 0) -> List:
    """Recursively search for review arrays in the data structure."""
    if depth > 8:
        return []

    if isinstance(data, list):
        if len(data) > 0:
            first = data[0] if len(data) > 0 else None
            if isinstance(first, list) and len(first) > 3:
                review_count = 0
                for item in data[:5]:
                    if isinstance(item, list):
                        has_text = any(isinstance(x, str) and len(x) > 20 for x in item[:10] if x)
                        has_rating = any(isinstance(x, int) and 1 <= x <= 5 for x in item[:10] if x)
                        if has_text or has_rating:
                            review_count += 1
                if review_count >= 2:
                    return data

        for item in data:
            result = find_reviews_in_data(item, depth + 1)
            if result:
                return result

    return []


def extract_single_review(review_data: List) -> Optional[Dict]:
    """Extract a single review from a review data array."""
    if not isinstance(review_data, list) or len(review_data) < 3:
        return None

    review = {}

    # Try to find author name - usually in first few elements
    for i in range(min(5, len(review_data))):
        item = review_data[i]
        if isinstance(item, list) and len(item) > 0:
            author = safe_get(item, 0, 1) or safe_get(item, 1)
            if isinstance(author, str) and len(author) > 1 and len(author) < 100:
                review['author'] = author
                break
        elif isinstance(item, str) and len(item) > 1 and len(item) < 100:
            if not item.startswith('http') and not any(c.isdigit() for c in item[:3]):
                review['author'] = item
                break

    # Find rating (integer 1-5)
    for i in range(min(10, len(review_data))):
        item = review_data[i]
        if isinstance(item, int) and 1 <= item <= 5:
            review['rating'] = item
            break

    # Find review text (longer string)
    for i in range(min(15, len(review_data))):
        item = review_data[i]
        if isinstance(item, str) and len(item) > 30:
            review['text'] = item
            break
        elif isinstance(item, list):
            for j in range(min(5, len(item))):
                if isinstance(item[j], str) and len(item[j]) > 30:
                    review['text'] = item[j]
                    break
            if review.get('text'):
                break

    # Find date string
    for i in range(min(20, len(review_data))):
        item = review_data[i]
        if isinstance(item, str):
            if 'ago' in item.lower() or 'week' in item.lower() or 'month' in item.lower() or 'year' in item.lower():
                review['date'] = item
                break
            if any(month in item.lower() for month in ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']):
                review['date'] = item
                break

    if review.get('author') or review.get('text'):
        return review
    return None


def extract_reviews_from_place_response(data: Any) -> List[Dict]:
    """
    Extract reviews from Google Maps /maps/preview/place response.

    Reviews are located at data[6][175][9][0][0] in the full response.
    Each review has:
    - [0][1][4][5][0] = Author name
    - [0][2][0][0] = Rating (1-5)
    - [0][1][6] = Date (e.g., "3 years ago")
    - [0][2][15][0][0] = Review text

    Args:
        data: Parsed JSON response from place preview endpoint

    Returns:
        List of review dictionaries
    """
    reviews = []

    place_data = safe_get(data, 6)
    if not place_data:
        place_data = data

    # Primary location: [6][175][9][0][0]
    reviews_array = safe_get(place_data, 175, 9, 0, 0)

    # Fallback to old location [6][52] if new location empty
    if not reviews_array or not isinstance(reviews_array, list):
        reviews_array = safe_get(place_data, 52)

    if not isinstance(reviews_array, list):
        reviews_array = find_reviews_in_data(data)

    if isinstance(reviews_array, list):
        for review_entry in reviews_array:
            if not isinstance(review_entry, list):
                continue

            # Try new structure first
            author = safe_get(review_entry, 0, 1, 4, 5, 0)
            rating = safe_get(review_entry, 0, 2, 0, 0)
            date = safe_get(review_entry, 0, 1, 6)
            text = safe_get(review_entry, 0, 2, 15, 0, 0)

            # If new structure worked, use it
            if author or text:
                review = {
                    'author': author,
                    'rating': rating if isinstance(rating, int) and 1 <= rating <= 5 else None,
                    'date': date,
                    'text': text,
                }
                if review.get('author') or review.get('text'):
                    reviews.append(review)
            else:
                # Fall back to old extraction method
                review = extract_single_review(review_entry)
                if review and review.get('author'):
                    reviews.append(review)

    return reviews


def extract_reviews(data: Any) -> List[Dict]:
    """
    Extract reviews from Google Maps review response.

    This handles the alternative review response format.

    Args:
        data: Parsed JSON response

    Returns:
        List of review dictionaries
    """
    reviews = []

    reviews_array = safe_get(data, 2)
    if not isinstance(reviews_array, list):
        reviews_array = data if isinstance(data, list) else []

    def find_reviews(obj, depth=0):
        if depth > 6:
            return

        if isinstance(obj, list):
            if len(obj) > 4:
                author = safe_get(obj, 0, 1) or safe_get(obj, 0)
                rating = None
                text = None
                date = None

                for i in range(min(10, len(obj))):
                    val = obj[i]
                    if isinstance(val, int) and 1 <= val <= 5:
                        rating = val
                        break

                for i in range(min(10, len(obj))):
                    val = obj[i]
                    if isinstance(val, str) and len(val) > 20:
                        text = val
                        break
                    elif isinstance(val, list):
                        for j in range(min(5, len(val))):
                            if isinstance(val[j], str) and len(val[j]) > 20:
                                text = val[j]
                                break

                for i in range(min(15, len(obj))):
                    val = obj[i]
                    if isinstance(val, str) and ('ago' in val.lower() or '202' in val or '201' in val):
                        date = val
                        break

                if author and isinstance(author, str) and (rating or text):
                    review = {
                        'author': author,
                        'rating': rating,
                        'text': text,
                        'date': date,
                    }

                    for i in range(min(20, len(obj))):
                        val = obj[i]
                        if isinstance(val, list) and len(val) > 0:
                            if isinstance(val[0], int) and val[0] > 0 and val[0] < 10000:
                                review['helpful_count'] = val[0]
                                break

                    reviews.append(review)
                    return

            for item in obj:
                find_reviews(item, depth + 1)

    find_reviews(reviews_array)

    # Deduplicate by author + text
    seen = set()
    unique_reviews = []
    for review in reviews:
        key = (review.get('author', ''), review.get('text', '')[:50] if review.get('text') else '')
        if key not in seen:
            seen.add(key)
            unique_reviews.append(review)

    return unique_reviews
