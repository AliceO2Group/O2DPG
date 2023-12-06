import os
import json
import argparse

# Embedded template qc configuration for MC
template_data = {
    "config": {
        "database": {
            "implementation": "CCDB",
            "host": "ccdb-test.cern.ch:8080",
            "username": "not_applicable",
            "password": "not_applicable",
            "name": "not_applicable"
        },
        "Activity": {
            "number": "42",
            "type": "2",
            "provenance": "qc_mc",
            "passName": "passMC",
            "periodName": "SimChallenge"
        },
        "monitoring": {
            "url": "no-op://"
        },
        "consul": {
            "url": ""
        },
        "conditionDB": {
            "url": "alice-ccdb.cern.ch"
        }
    }
}

def update_json_files(folder_path):
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

    args = parser.parse_args()

    update_json_files(args.folder_path)

if __name__ == "__main__":
    main()

