import json
import os
import requests
import subprocess

import dataclasses # to define the MCProdInfo data layout and convert it to dict
from dataclasses import dataclass, field, asdict, fields
from typing import Optional
import hashlib

@dataclass(frozen=True)
class MCProdInfo:
    """
    struct for MonteCarlo production info
    """
    LPMProductionTag: str
    Col: int
    IntRate: float   # only indicative of some interaction rate (could vary within the run)
    RunNumber: int
    OrbitsPerTF: int
    # max_events_per_tf: Optional[int] = -1
    Comment: Optional[str] = None
    McTag: Optional[str] = None # main software tag used 
    RecoTag: Optional[str] = None # RecoTag (if any)
    Hash: Optional[str] = field(default=None)

    def __post_init__(self):
        if self.Hash == None:
           # Hash only the meaningful fields
            data_to_hash = {
                k: v for k, v in asdict(self).items()
                if k != 'Hash'
            }
            hash_str = hashlib.sha256(
                json.dumps(data_to_hash, sort_keys=True).encode()
            ).hexdigest()
            object.__setattr__(self, 'Hash', hash_str)


import re

def extract_metadata_blocks_from_CCDB(text: str):
    blocks = []
    # Split on 'Metadata:\n' and iterate over each block
    sections = text.split('Metadata:\n')
    for section in sections[1:]:  # skip the first chunk (before any Metadata:)
        metadata = {}
        for line in section.splitlines():
            if not line.strip():  # stop at first blank line
                break
            match = re.match(r'\s*(\w+)\s*=\s*(.+)', line)
            if match:
                key, val = match.groups()
                # Type conversion
                if val == "None":
                    val = None
                elif val.isdigit() or (val.startswith('-') and val[1:].isdigit()):
                    val = int(val)
                else:
                    try:
                        val = float(val)
                    except ValueError:
                        val = val.strip()
                metadata[key] = val
        if metadata:
            blocks.append(metadata)
    return blocks



def query_mcprodinfo(base_url, user, run_number, lpm_prod_tag, cert_dir="/tmp"):
    """
    Queries MCProdInfo from CCDB. Returns object or None
    """
    # check if the tokenfiles are there
    key_path = os.environ.get("JALIEN_TOKEN_KEY")
    cert_path = os.environ.get("JALIEN_TOKEN_CERT")
    if key_path == None and cert_path == None:
       uid = os.getuid()
       cert_path = os.path.join(cert_dir, f"tokencert_{uid}.pem")
       key_path = os.path.join(cert_dir, f"tokenkey_{uid}.pem")

    # Build full URL
    user_path = 'Users/' + user[0] + '/' + user
    start = run_number
    stop = run_number + 1 
    url = f"{base_url}/browse/{user_path}/MCProdInfo/{lpm_prod_tag}/{start}/{stop}"

    response = requests.get(url, cert=(cert_path, key_path), verify=False)
    if response.status_code != 404:
        meta = extract_metadata_blocks_from_CCDB(response.content.decode('utf-8'))
        if (len(meta) > 0):
          def filter_known_fields(cls, data: dict) -> dict:
            valid_keys = {f.name for f in fields(cls)}
            return {k: v for k, v in data.items() if k in valid_keys}
        
          clean_meta = filter_known_fields(MCProdInfo, meta[0])
          return MCProdInfo(**clean_meta)
       
    return None


def upload_mcprodinfo_meta(base_url, user, run_number, lpm_prod_tag, keys, cert_dir="/tmp"):
    """
    Uploads an empty .dat file using client certificates.

    Parameters:
    - base_url (str): The base HTTPS URL, e.g., "https://URL"
    - user (str): The uploader --> Determines location "Users/f/foo_bar/MCProdInfo/..."
    - keys (dict): Dictionary with meta information to upload, e.g., {"key1": "var1", "key2": "var2"}
    - cert_dir (str): Directory where the .pem files are located (default: /tmp)

    Returns:
    - Response object from the POST request
    """
    # Create an empty file
    empty_file = "empty.dat"
    with open(empty_file, "w") as f:
        f.write("0")

    # Construct user ID-specific cert and key paths
    key_path = os.environ.get("JALIEN_TOKEN_KEY")
    cert_path = os.environ.get("JALIEN_TOKEN_CERT")
    if key_path == None and cert_path == None:
       uid = os.getuid()
       cert_path = os.path.join(cert_dir, f"tokencert_{uid}.pem")
       key_path = os.path.join(cert_dir, f"tokenkey_{uid}.pem")
    
    # Build full URL
    query = "/".join(f"{k}={v}" for k, v in keys.items())
    user_path = 'Users/' + user[0] + '/' + user
    start = run_number
    stop = run_number + 1 
    url = f"{base_url}/{user_path}/MCProdInfo/{lpm_prod_tag}/{start}/{stop}/{query}"

    print (f"Full {url}")
    
    # Prepare request
    with open(empty_file, 'rb') as f:
        files = {'blob': f}
        response = requests.post(url, files=files, cert=(cert_path, key_path), verify=False)

    # Optional: remove the temporary file
    os.remove(empty_file)

    return response

def publish_MCProdInfo(mc_prod_info, ccdb_url = "https://alice-ccdb.cern.ch", username = "aliprod", force_overwrite=False, include_meta_into_aod=False):
   print("Publishing MCProdInfo")

   if mc_prod_info.LPMProductionTag == None or len(mc_prod_info.LPMProductionTag) == 0:
       print ("No LPM production tag found; Not publishing")
       return

   # see if this already has meta-data uploaded, otherwise do nothing
   mc_prod_info_q = query_mcprodinfo(ccdb_url, username, mc_prod_info.RunNumber, mc_prod_info.LPMProductionTag)
   if mc_prod_info_q == None or force_overwrite == True:
    # could make this depend on hash values in future
    upload_mcprodinfo_meta(ccdb_url, username, mc_prod_info.RunNumber, mc_prod_info.LPMProductionTag, dataclasses.asdict(mc_prod_info))

