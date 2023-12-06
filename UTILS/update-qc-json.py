import os
import json
import argparse

def update_json_files(folder_path, template_file):

    with open(template_file, 'r') as file:
        template_data = json.load(file)

    # Iterate over files in the specified folder
    for filename in os.listdir(folder_path):
        if filename.endswith('.json'):
            file_path = os.path.join(folder_path, filename)

            # Read the content of the JSON file
            with open(file_path, 'r') as file:
                data = json.load(file)

            # Check if 'qc' and 'config' sections exist and then update
            if 'qc' in data and 'config' in data['qc']:
                data['qc']['config'] = template_data['config']

            # Write the updated content back to the JSON file
            with open(file_path, 'w') as file:
                json.dump(data, file, indent=2)

def main():
    parser = argparse.ArgumentParser(description="Update the 'config' section in the 'qc' part of JSON files in a folder.")
    parser.add_argument('folder_path', type=str, help='Path to the folder containing JSON files')
    parser.add_argument('template_file', type=str, help='JSON template file')

    args = parser.parse_args()

    update_json_files(args.folder_path, args.template_file)

if __name__ == "__main__":
    main()

