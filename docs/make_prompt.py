import json
import os


def extract_prompt():
    file_path = "prompts.json"
    output_path = "user_input.txt"

    if not os.path.exists(file_path):
        print(f"Error: {file_path} not found.")
        return

    try:
        with open(file_path, "r") as f:
            data = json.load(f)

        if isinstance(data, dict):
            sorted_keys = sorted(data.keys())
            prompts = [data[k] for k in sorted_keys]
        elif isinstance(data, list):
            prompts = data
        else:
            print("Unexpected JSON format.")
            return

        if not prompts:
            print("No prompts found.")
            return

        print(f"Found {len(prompts)} prompts.")
        selection = int(input(f"Pick a number (1 to {len(prompts)}): "))

        if 1 <= selection <= len(prompts):
            selected_item = prompts[selection - 1]

            # More aggressive text extraction
            if isinstance(selected_item, dict):
                # Check common keys used in prompt files
                for key in ["prompt", "text", "content", "body"]:
                    if key in selected_item:
                        text_content = str(selected_item[key])
                        break
                else:
                    # If no common key, just take the first string value
                    text_content = next(
                        (str(v) for v in selected_item.values() if isinstance(v, str)),
                        str(selected_item),
                    )
            else:
                text_content = str(selected_item)

            # Ensure it is just the string, no quotes or braces from JSON
            if (text_content.startswith("{") and text_content.endswith("}")) or (
                text_content.startswith('"') and text_content.endswith('"')
            ):
                try:
                    # Try to parse again if it looks like a JSON string within a string
                    temp = json.loads(text_content)
                    if isinstance(temp, str):
                        text_content = temp
                except:
                    pass

            final_text = text_content.strip('"{}[] ')

            with open(output_path, "w") as out_file:
                out_file.write(final_text)

            print(f"Successfully saved pure text to {output_path}.")
        else:
            print("Selection out of range.")

    except Exception as e:
        print(f"Error: {e}")



if __name__ == "__main__":
    extract_prompt()
