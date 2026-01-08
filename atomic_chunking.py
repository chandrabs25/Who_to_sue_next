import json
import re
import os


def parse_atomic_units(text):
    """
    Splits legal text into atomic units based on numbering ((1), (a))
    and specific legal clauses (Provided that).
    """
    # Clean basic formatting
    clean_text = text.replace("\r\n", " ").replace("\n", " ").strip()

    # Define Split Pattern: Markers like (1), (a), or "Provided that"
    pattern = r'(\(\w+\)|Provided that)'

    parts = re.split(pattern, clean_text)

    chunks = []
    current_chunk = ""

    for part in parts:
        part = part.strip()
        if not part:
            continue

        if re.match(pattern, part):
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = part
        else:
            current_chunk += " " + part

    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks


def process_file(input_filename, output_filename):
    if not os.path.exists(input_filename):
        print(f"Error: {input_filename} not found.")
        return

    with open(input_filename, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if isinstance(data, dict):
        data = [data]

    processed_data = []

    for chapter in data:
        chapter_name = chapter.get("chapter_name", "Unknown Chapter")
        processed_sections = []

        for section in chapter.get("sections", []):
            title = section.get("title", "")
            sec_id = section.get("section", "")
            raw_content = section.get("content", "")

            # 1. Get the list of raw text chunks
            atomic_units_text = parse_atomic_units(raw_content)

            atomic_units_objects = []

            # 2. Iterate to build enriched objects
            for i, unit_text in enumerate(atomic_units_text):

                # Determine type
                is_proviso = unit_text.startswith("Provided")
                unit_type = "proviso" if is_proviso else "clause"

                # --- NEW LOGIC: SEMANTIC ANCHORING ---
                # If it is a proviso, grab the context of the PREVIOUS chunk.
                # This anchors the exception to the rule it likely modifies.
                anchor_text = ""
                if is_proviso and i > 0:
                    prev_text = atomic_units_text[i - 1]
                    # Truncate prev_text if it's too long to avoid token bloat (optional)
                    anchor_text = f"[Context from Preceding Clause: {prev_text[:200]}...] "

                # Build the String for the Embedding Model
                # Format: Chapter | Section | [Anchor] Content
                context_str = (
                    f"Chapter: {chapter_name} | "
                    f"Section: {sec_id} {title} | "
                    f"Content: {anchor_text}{unit_text}"
                )

                atomic_units_objects.append({
                    "chunk_index": i,
                    "unit_type": unit_type,
                    "text": unit_text,  # Clean text for display
                    "enriched_context": context_str,  # Anchored text for vector search
                    "parent_section_id": sec_id
                })

            processed_sections.append({
                "section_id": sec_id,
                "title": title,
                "original_content": raw_content,
                "atomic_units": atomic_units_objects
            })

        processed_data.append({
            "chapter_name": chapter_name,
            "sections": processed_sections
        })

    with open(output_filename, 'w', encoding='utf-8') as f:
        json.dump(processed_data, f, indent=4, ensure_ascii=False)

    print(f"Success! Processed data with Semantic Anchors saved to: {output_filename}")


# --- Execution Block ---
if __name__ == "__main__":

    dummy_input = "clean_data.json"


    process_file(dummy_input, "cpa_anchored.json")