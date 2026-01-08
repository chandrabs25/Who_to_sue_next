import json
import re


def process_legal_json(input_filepath, output_filepath):
    """
    Reads a JSON file, cleans the title, extracts section numbers,
    removes URLs, and saves to a new file.
    """

    # 1. Load the data
    try:
        with open(input_filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: The file '{input_filepath}' was not found.")
        return
    except json.JSONDecodeError:
        print(f"Error: Failed to decode JSON from '{input_filepath}'. check format.")
        return

    # Regex pattern breakdown:
    # ^Section\s+  -> Matches text starting with "Section" followed by space(s)
    # ([\w\d]+)    -> Group 1: Captures the section number (alphanumeric to catch '2A' etc)
    # \.           -> Matches the literal dot separator
    # (.*)         -> Group 2: Captures the rest of the title string
    pattern = re.compile(r"^Section\s+([\w\d]+)\.(.*)", re.DOTALL)

    # 2. Process the list
    for chapter in data:
        if "sections" in chapter:
            for item in chapter["sections"]:

                # --- Remove URL key ---
                if "url" in item:
                    del item["url"]

                # --- Process Title and Extract Section ID ---
                original_title = item.get("title", "")

                # Check if the title matches the "Section X." pattern
                match = pattern.match(original_title)

                if match:
                    section_num = match.group(1)  # e.g., "1"
                    clean_title = match.group(2).strip()  # e.g., "Short title..."

                    item["section"] = section_num
                    item["title"] = clean_title
                else:
                    # Fallback if a title doesn't follow the standard format
                    item["section"] = None

                    # 3. Write the output
    with open(output_filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

    print(f"Success! Processed data saved to '{output_filepath}'")


# --- Usage Example ---
if __name__ == "__main__":
    # create a dummy file for testing based on your prompt
    input_filename = "consumer_protection_act_2019.json"
    output_filename = "clean_data.json"

    process_legal_json(input_filename, output_filename)