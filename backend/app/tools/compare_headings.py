#!/usr/bin/env python3
import json

def count_heading_nodes(file_path):
    """Count the actual number of heading nodes in a lesson JSON file"""
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    heading_count = 0

    for lesson in data:
        for section in lesson.get('sections', []):
            for item in section.get('content_jsonb', []):
                if item.get('kind') == 'heading':
                    heading_count += 1

    return heading_count

def extract_heading_nodes_with_position(file_path):
    """Extract all heading nodes with their position and context from a lesson JSON file"""
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    heading_nodes = []

    for lesson in data:
        lesson_external_id = lesson.get('lesson', {}).get('external_id', 'Unknown')
        lesson_title = lesson.get('lesson', {}).get('title', 'Unknown')

        for section_index, section in enumerate(lesson.get('sections', [])):
            section_type = section.get('type', 'unknown')

            for item_index, item in enumerate(section.get('content_jsonb', [])):
                if item.get('kind') == 'heading':
                    # Extract heading text
                    text_field = item.get('text')
                    lesson_context = item.get('lesson_context', 'Unknown')

                    heading_text = "NO_TEXT"
                    en_text = ""
                    th_text = ""

                    if isinstance(text_field, dict):
                        # Handle bilingual headings with en/th structure
                        en_text = text_field.get('en', '') or ''
                        th_text = text_field.get('th', '') or ''
                        if en_text and th_text:
                            heading_text = f"{en_text} / {th_text}"
                        elif en_text:
                            heading_text = en_text
                        elif th_text:
                            heading_text = th_text
                    elif isinstance(text_field, str):
                        heading_text = text_field.strip()
                        # Try to extract English part if it's a combined string
                        if ' ' in heading_text:
                            parts = heading_text.split()
                            # Simple heuristic: if first part is all ASCII, it might be English
                            if all(ord(c) < 128 for c in parts[0]):
                                en_text = parts[0]
                    else:
                        # Check inlines for heading text
                        inlines = item.get('inlines', [])
                        text_parts = []
                        for inline in inlines:
                            text = inline.get('text', '').strip()
                            if text:
                                text_parts.append(text)
                        if text_parts:
                            heading_text = ' '.join(text_parts)
                            # For inlines, the full text is often the English text
                            en_text = heading_text

                    heading_nodes.append({
                        'text': heading_text,
                        'en_text': en_text.strip(),
                        'th_text': th_text.strip(),
                        'lesson_id': lesson_external_id,
                        'lesson_title': lesson_title,
                        'section_type': section_type,
                        'section_index': section_index,
                        'item_index': item_index,
                        'lesson_context': lesson_context,
                        'position_key': f"{lesson_external_id}_{section_index}_{item_index}"
                    })

    return heading_nodes

def find_unmatched_thai_headings(en_nodes, th_nodes):
    """Find Thai headings that don't have a corresponding English heading in the same position"""

    # Create a map of English headings by position and text
    en_position_map = {}
    en_text_set = set()

    for en_node in en_nodes:
        position_key = en_node['position_key']
        en_text = en_node['en_text']

        en_position_map[position_key] = en_node
        if en_text:
            en_text_set.add(en_text.upper())  # Case insensitive comparison

    unmatched_thai = []

    for th_node in th_nodes:
        position_key = th_node['position_key']
        th_text = th_node['text']
        th_en_text = th_node['en_text']

        is_matched = False

        # Check if there's an English heading at the same position
        if position_key in en_position_map:
            en_node = en_position_map[position_key]
            en_text = en_node['en_text']

            # Check if the English text matches or is contained
            if en_text and (en_text.upper() in th_text.upper() or th_en_text.upper() == en_text.upper()):
                is_matched = True

        # Also check if any English heading text appears in this Thai heading
        if not is_matched:
            for en_text in en_text_set:
                if en_text and en_text in th_text.upper():
                    is_matched = True
                    break

        if not is_matched:
            unmatched_thai.append(th_node)

    return unmatched_thai

def extract_headings_with_context(file_path):
    """Extract all heading texts with their lesson context from a lesson JSON file"""
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    headings_with_context = {}

    for lesson in data:
        lesson_external_id = lesson.get('lesson', {}).get('external_id', 'Unknown')
        lesson_title = lesson.get('lesson', {}).get('title', 'Unknown')

        for section in lesson.get('sections', []):
            section_type = section.get('type', 'unknown')

            for item in section.get('content_jsonb', []):
                if item.get('kind') == 'heading':
                    # Check if heading has text field
                    text_field = item.get('text')
                    lesson_context = item.get('lesson_context', 'Unknown')

                    context_info = {
                        'lesson_id': lesson_external_id,
                        'lesson_title': lesson_title,
                        'section_type': section_type,
                        'lesson_context': lesson_context
                    }

                    if isinstance(text_field, dict):
                        # Handle bilingual headings with en/th structure
                        en_text = text_field.get('en', '') or ''
                        th_text = text_field.get('th', '') or ''
                        en_text = en_text.strip()
                        th_text = th_text.strip()
                        if en_text:
                            headings_with_context[en_text] = context_info
                        if th_text:
                            headings_with_context[th_text] = context_info
                    elif isinstance(text_field, str):
                        # Handle string headings
                        heading_text = text_field.strip()
                        if heading_text:
                            headings_with_context[heading_text] = context_info
                    else:
                        # Check inlines for heading text
                        inlines = item.get('inlines', [])
                        for inline in inlines:
                            text = inline.get('text', '').strip()
                            if text:
                                headings_with_context[text] = context_info

    return headings_with_context

def main():
    import os

    # Use relative paths from the backend directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.dirname(os.path.dirname(script_dir))
    data_dir = os.path.join(backend_dir, 'data')

    en_file = os.path.join(data_dir, 'level_1.json')
    th_file = os.path.join(data_dir, 'level_1_th.json')
    output_file = os.path.join(data_dir, 'heading_comparison_results.txt')

    print("Counting heading nodes in English file...")
    en_heading_count = count_heading_nodes(en_file)
    print(f"Found {en_heading_count} heading nodes in English file")

    print("\nCounting heading nodes in Thai file...")
    th_heading_count = count_heading_nodes(th_file)
    print(f"Found {th_heading_count} heading nodes in Thai file")

    print(f"\nDifference: {th_heading_count - en_heading_count} more heading nodes in Thai file")

    print("\nExtracting heading nodes with position from both files...")
    en_heading_nodes = extract_heading_nodes_with_position(en_file)
    th_heading_nodes = extract_heading_nodes_with_position(th_file)

    print(f"English file has {len(en_heading_nodes)} heading nodes")
    print(f"Thai file has {len(th_heading_nodes)} heading nodes")

    # Find Thai headings that don't match any English headings
    unmatched_thai_nodes = find_unmatched_thai_headings(en_heading_nodes, th_heading_nodes)

    print(f"\nFound {len(unmatched_thai_nodes)} Thai heading nodes that don't match any English headings:")    # Write results to file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("HEADING COMPARISON RESULTS\n")
        f.write("=" * 50 + "\n\n")
        f.write(f"English file: {en_file}\n")
        f.write(f"Thai file: {th_file}\n\n")
        f.write(f"Total heading nodes in English file: {en_heading_count}\n")
        f.write(f"Total heading nodes in Thai file: {th_heading_count}\n")
        f.write(f"Difference: {th_heading_count - en_heading_count} more heading nodes in Thai file\n\n")

        f.write(f"THAI HEADING NODES THAT DON'T MATCH ANY ENGLISH HEADINGS ({len(unmatched_thai_nodes)} total):\n")
        f.write("-" * 40 + "\n")
        for i, node in enumerate(unmatched_thai_nodes, 1):
            f.write(f"{i:2d}. {node['text']}\n")
            f.write(f"    Lesson: {node['lesson_id']} - {node['lesson_title']}\n")
            f.write(f"    Section: {node['section_type']}\n")
            f.write(f"    Context: {node['lesson_context']}\n\n")

            print(f"{i:2d}. {node['text']}")
            print(f"    Lesson: {node['lesson_id']} - {node['lesson_title']}")
            print(f"    Section: {node['section_type']}")
            print(f"    Context: {node['lesson_context']}")
            print()

    print(f"\nResults written to: {output_file}")

if __name__ == "__main__":
    main()
