"""
Google Maps PB Decoder - Web UI

A Streamlit-based web interface for decoding Google Maps pb parameters.

Run with: streamlit run app.py
"""

import streamlit as st
import json
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pb_decoder.curl_parser import parse_curl
from pb_decoder.pb_decoder import decode_pb_to_flat, decode_pb_to_dict
from pb_decoder.main_decoder import decode_google_maps_curl, DecodedRequest


# Page config
st.set_page_config(
    page_title="Google Maps PB Decoder",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1a73e8;
        margin-bottom: 1rem;
    }
    .section-header {
        font-size: 1.3rem;
        font-weight: bold;
        color: #333;
        margin-top: 1.5rem;
        margin-bottom: 0.5rem;
        padding-bottom: 0.3rem;
        border-bottom: 2px solid #1a73e8;
    }
    .param-key {
        font-family: monospace;
        background-color: #e8f0fe;
        padding: 2px 6px;
        border-radius: 3px;
        color: #1a73e8;
    }
    .param-value {
        font-family: monospace;
        background-color: #f1f3f4;
        padding: 2px 6px;
        border-radius: 3px;
    }
    .extracted-value {
        font-size: 1.1rem;
        padding: 0.5rem;
        background-color: #e8f5e9;
        border-radius: 5px;
        margin: 0.2rem 0;
    }
    .stTextArea textarea {
        font-family: monospace;
        font-size: 12px;
    }
    .pb-field {
        font-family: monospace;
        padding: 4px 8px;
        margin: 2px 0;
        background-color: #fafafa;
        border-left: 3px solid #1a73e8;
    }
    .pb-field-nested {
        margin-left: 20px;
        border-left-color: #34a853;
    }
    .pb-field-nested-2 {
        margin-left: 40px;
        border-left-color: #fbbc04;
    }
    .pb-field-nested-3 {
        margin-left: 60px;
        border-left-color: #ea4335;
    }
</style>
""", unsafe_allow_html=True)


def main():
    # Header
    st.markdown('<div class="main-header">🗺️ Google Maps PB Decoder</div>', unsafe_allow_html=True)
    st.markdown("Decode Google Maps request parameters from curl commands")

    # Sidebar
    with st.sidebar:
        st.header("ℹ️ About")
        st.markdown("""
        This tool decodes Google Maps search requests, specifically the `pb` parameter
        which uses a protobuf-like text encoding.

        **How to use:**
        1. Copy a curl command from browser DevTools
        2. Paste it in the text area
        3. Click "Decode"

        **PB Format:**
        - `!{field}{type}{value}`
        - Types: `s`=string, `i`=int, `d`=double, `b`=bool, `m`=message, `e`=enum, `f`=float
        """)

        st.header("🔑 Key Parameters")
        st.markdown("""
        | Parameter | Meaning |
        |-----------|---------|
        | `!1s` | Search query |
        | `!2d` | Longitude |
        | `!3d` | Latitude |
        | `!1d` | Viewport distance |
        | `!7i` | Results count |
        | `!8i` | Offset (pagination) |
        | `!74i` | Max search radius |
        | `!4f` | Zoom level |
        """)

    # Main content
    col1, col2 = st.columns([1, 1])

    with col1:
        st.markdown('<div class="section-header">📥 Input</div>', unsafe_allow_html=True)

        # Input text area
        curl_input = st.text_area(
            "Paste your curl command here:",
            height=300,
            placeholder="curl 'https://www.google.com/search?tbm=map&...' -H '...'",
            key="curl_input"
        )

        # Decode button
        decode_clicked = st.button("🔍 Decode", type="primary", use_container_width=True)

    # Process and display results
    if decode_clicked and curl_input:
        try:
            result = decode_google_maps_curl(curl_input)

            with col2:
                display_results(result)

            # Full details below
            st.markdown("---")
            display_full_details(result)

        except Exception as e:
            st.error(f"Error decoding request: {str(e)}")
            st.exception(e)

    elif decode_clicked:
        st.warning("Please paste a curl command first.")


def display_results(result: DecodedRequest):
    """Display the decoded results summary"""
    st.markdown('<div class="section-header">📊 Decoded Summary</div>', unsafe_allow_html=True)

    # Extracted key values
    st.markdown("#### 🎯 Key Values")

    col_a, col_b = st.columns(2)

    with col_a:
        if result.search_query:
            st.metric("Search Query", result.search_query)
        if result.latitude is not None:
            st.metric("Latitude", f"{result.latitude:.6f}")
        if result.longitude is not None:
            st.metric("Longitude", f"{result.longitude:.6f}")
        if result.zoom_level is not None:
            st.metric("Zoom Level", result.zoom_level)

    with col_b:
        if result.results_count is not None:
            st.metric("Results Count (!7i)", result.results_count)
        if result.offset is not None:
            st.metric("Offset (!8i)", result.offset)
        if result.viewport_distance is not None:
            st.metric("Viewport Distance", f"{result.viewport_distance:,.0f}m")
        if result.max_radius is not None:
            st.metric("Max Radius (!74i)", f"{result.max_radius:,}m")

    # URL Parameters
    st.markdown("#### 🔗 URL Parameters")
    if result.url_params:
        params_df_data = [{"Parameter": k, "Value": v} for k, v in result.url_params.items()]
        st.dataframe(params_df_data, use_container_width=True, hide_index=True)
    else:
        st.info("No URL parameters found")


def display_full_details(result: DecodedRequest):
    """Display full decoded details in tabs"""

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📋 PB Parameters (Flat)",
        "🌳 PB Parameters (Tree)",
        "📨 Headers",
        "🍪 Cookies",
        "📄 Raw JSON"
    ])

    with tab1:
        display_pb_flat(result.pb_flat)

    with tab2:
        display_pb_tree(result.pb_decoded)

    with tab3:
        display_headers(result.headers)

    with tab4:
        display_cookies(result.cookies)

    with tab5:
        display_raw_json(result)


def display_pb_flat(pb_flat):
    """Display pb parameters in flat format"""
    st.markdown("### PB Parameters (Flat View)")

    if not pb_flat:
        st.info("No PB parameters to display")
        return

    # Create a searchable/filterable table
    search = st.text_input("🔍 Filter parameters:", placeholder="e.g., '7i' or 'latitude'")

    filtered = pb_flat
    if search:
        search_lower = search.lower()
        filtered = [
            entry for entry in pb_flat
            if search_lower in str(entry.get('path', '')).lower()
            or search_lower in str(entry.get('value', '')).lower()
            or search_lower in str(entry.get('description', '')).lower()
        ]

    # Display as table
    table_data = []
    for entry in filtered:
        table_data.append({
            "Path": entry.get('path', ''),
            "Field": entry.get('field', ''),
            "Type": entry.get('type_name', ''),
            "Value": str(entry.get('value', '')),
            "Description": entry.get('description', ''),
        })

    if table_data:
        st.dataframe(table_data, use_container_width=True, hide_index=True, height=400)
        st.caption(f"Showing {len(table_data)} of {len(pb_flat)} parameters")
    else:
        st.info("No matching parameters found")


def display_pb_tree(pb_decoded):
    """Display pb parameters in tree format"""
    st.markdown("### PB Parameters (Tree View)")

    if not pb_decoded:
        st.info("No PB parameters to display")
        return

    # Render as expandable tree
    for field in pb_decoded:
        render_field_tree(field, 0)


def render_field_tree(field: dict, depth: int):
    """Recursively render a field as a tree"""
    indent = "  " * depth
    field_num = field.get('field', '?')
    field_type = field.get('type', '?')
    type_name = field.get('type_name', '')
    value = field.get('value', '')
    description = field.get('description', '')
    children = field.get('children', [])

    # Format the field line
    if field_type == 'm':
        label = f"📁 **!{field_num}m{value}**"
        if description:
            label += f" - _{description}_"

        with st.expander(label, expanded=(depth < 2)):
            for child in children:
                render_field_tree(child, depth + 1)
    else:
        type_emoji = {
            's': '📝',
            'i': '🔢',
            'd': '📊',
            'b': '✅' if value else '❌',
            'e': '📋',
            'f': '📊',
        }.get(field_type, '❓')

        line = f"{type_emoji} `!{field_num}{field_type}` = **{value}** ({type_name})"
        if description:
            line += f" - _{description}_"

        st.markdown(line)


def display_headers(headers: dict):
    """Display HTTP headers"""
    st.markdown("### HTTP Headers")

    if not headers:
        st.info("No headers found")
        return

    table_data = [{"Header": k, "Value": v} for k, v in headers.items()]
    st.dataframe(table_data, use_container_width=True, hide_index=True)


def display_cookies(cookies: dict):
    """Display cookies"""
    st.markdown("### Cookies")

    if not cookies:
        st.info("No cookies found")
        return

    table_data = [{"Cookie": k, "Value": v[:50] + "..." if len(v) > 50 else v} for k, v in cookies.items()]
    st.dataframe(table_data, use_container_width=True, hide_index=True)


def display_raw_json(result: DecodedRequest):
    """Display raw JSON output"""
    st.markdown("### Raw JSON Output")

    json_output = result.to_json(indent=2)

    st.download_button(
        label="📥 Download JSON",
        data=json_output,
        file_name="decoded_request.json",
        mime="application/json"
    )

    st.code(json_output, language="json")


if __name__ == "__main__":
    main()
