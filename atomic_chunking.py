import json
import re
import os


def parse_atomic_units(text):

    clean_text = text.replace("\r\n", " ").replace("\n", " ").strip()

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


def parse_definitions_by_quotes(text):

    clean_text = text.replace("\r\n", " ").replace("\n", " ").strip()

    # Matches (1) "advertisement"
    pattern = r'(\(\d+\)\s*".+?")'

    parts = re.split(pattern, clean_text)

    definitions = []
    current_header = ""

    for part in parts:
        part = part.strip()
        if not part:
            continue

        if re.match(pattern, part):
            current_header = part
        elif current_header:
            full_definition = f"{current_header} {part}"
            definitions.append(full_definition)
            current_header = ""
        else:
            pass

    return definitions


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

            atomic_units_objects = []

            # --- BRANCHING LOGIC ---
            if str(sec_id) == "2":
                # STRATEGY FOR DEFINITIONS
                raw_chunks = parse_definitions_by_quotes(raw_content)

                for i, unit_text in enumerate(raw_chunks):
                    # --- NEW LOGIC: Extract the Term ---
                    # Finds the first text inside double quotes, e.g., "consumer"
                    term_match = re.search(r'"(.+?)"', unit_text)
                    term_value = term_match.group(1) if term_match else "Unknown"

                    context_str = (
                        f"Chapter: {chapter_name} | "
                        f"Section: {sec_id} {title} | "
                        f"Definition: {unit_text}"
                    )

                    atomic_units_objects.append({
                        "chunk_index": i,
                        "unit_type": "definition",
                        "term": term_value,  # <--- NEW KEY ADDED HERE
                        "text": unit_text,
                        "enriched_context": context_str,
                        "parent_section_id": sec_id
                    })

            else:
                # STRATEGY FOR STANDARD SECTIONS
                raw_chunks = parse_atomic_units(raw_content)

                for i, unit_text in enumerate(raw_chunks):
                    is_proviso = unit_text.startswith("Provided")
                    unit_type = "proviso" if is_proviso else "clause"

                    anchor_text = ""
                    if is_proviso and i > 0:
                        prev_text = raw_chunks[i - 1]
                        anchor_text = f"[Context from Preceding Clause: {prev_text[:200]}...] "

                    context_str = (
                        f"Chapter: {chapter_name} | "
                        f"Section: {sec_id} {title} | "
                        f"Content: {anchor_text}{unit_text}"
                    )

                    atomic_units_objects.append({
                        "chunk_index": i,
                        "unit_type": unit_type,
                        "text": unit_text,
                        "enriched_context": context_str,
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

    print(f"Success! Processed data saved to: {output_filename}")


# --- Execution Block ---
if __name__ == "__main__":
    input = "clean_data.json"
    process_file(input, "cpa_anchored_refined_v2.json")