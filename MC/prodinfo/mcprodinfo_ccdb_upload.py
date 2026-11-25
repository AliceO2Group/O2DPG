import json
import os
import requests
import urllib.parse
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
    FirstOrbitMC: Optional[int] = None # first orbit used by the MC; its TFs start at FirstOrbitMC + k * OrbitsPerTF
    OutputDir: Optional[str] = None # output directory of the production (without run and subjob parts)
    MasterJobID: Optional[int] = None # GRID masterjob of the writer; orders versions written by different cycles
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

def extract_metadata_blocks_from_CCDB(text: str, convert=True):
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
                # CCDB keeps metadata URL-encoded as uploaded, e.g. %2F for a slash
                val = urllib.parse.unquote(val)
                # Type conversion
                if val == "None":
                    val = None
                elif not convert:
                    val = val.strip()
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


def extract_newest_metadata_from_CCDB(text: str, convert=True):
    """
    Metadata of the most recently created object in a CCDB browse listing, or None
    """
    newest, newest_key = None, None
    for section in re.split(r'\n(?=ID: )', text):
        blocks = extract_metadata_blocks_from_CCDB(section, convert)
        if not blocks:
            continue
        m = re.search(r'^Created:\s*(\d+)', section, re.M)
        i = re.search(r'^ID:\s*(\S+)', section, re.M)
        # equal creation times are ordered by ID
        key = (int(m.group(1)) if m else -1, i.group(1) if i else "")
        if newest == None or key > newest_key:
            newest, newest_key = blocks[0], key
    return newest


def production_output_dir(job_output_dir, run_number):
    """
    Output directory of a production from a job's OutputDir, e.g.
    /alice/sim/2026/LHC26h3_dev2/0/572196/001 -> /alice/sim/2026/LHC26h3_dev2/0 . None if the run is not part of it.
    """
    if not job_output_dir:
        return None
    parts = job_output_dir.rstrip('/').split('/')
    if str(run_number) not in parts:
        return None
    return '/'.join(parts[:parts.index(str(run_number))]) or None



def query_mcprodinfo(base_url, user, run_number, lpm_prod_tag, cert_dir="/tmp", raw=False):
    """
    Queries MCProdInfo from CCDB. Returns object or None.
    With raw, returns (object, metadata strings as stored) or (None, None).
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
    if response.status_code not in (200, 404):
        raise RuntimeError(f"CCDB query {url} failed with HTTP {response.status_code}")
    if response.status_code == 200:
        # several versions can exist; the newest one is the current one
        text = response.content.decode('utf-8')
        newest = extract_newest_metadata_from_CCDB(text)
        if newest != None:
          def filter_known_fields(cls, data: dict) -> dict:
            valid_keys = {f.name for f in fields(cls)}
            return {k: v for k, v in data.items() if k in valid_keys}
        
          clean_meta = filter_known_fields(MCProdInfo, newest)
          # an object may lack fields that are required here (not every writer sets all of them)
          for f in fields(MCProdInfo):
            clean_meta.setdefault(f.name, None)
          info = MCProdInfo(**clean_meta)
          if raw:
            return info, filter_known_fields(MCProdInfo, extract_newest_metadata_from_CCDB(text, convert=False))
          return info

    return (None, None) if raw else None


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
    optional = {f.name for f in fields(MCProdInfo) if f.default is not dataclasses.MISSING}
    query = "/".join(f"{k}={urllib.parse.quote(str(v), safe='@:,')}" for k, v in keys.items() if v is not None or k not in optional)
    user_path = 'Users/' + user[0] + '/' + user
    start = run_number
    stop = run_number + 1 
    url = f"{base_url}/{user_path}/MCProdInfo/{lpm_prod_tag}/{start}/{stop}/{query}"

    print (f"Full {url}")
    
    # Prepare request
    with open(empty_file, 'rb') as f:
        files = {'blob': f}
        response = requests.post(url, files=files, cert=(cert_path, key_path), verify=False)
    if not 200 <= response.status_code < 300:
        print(f"WARNING: upload of MCProdInfo to {url} failed with HTTP {response.status_code}: {response.text[:300]}")

    # Optional: remove the temporary file
    os.remove(empty_file)

    return response

# fields that describe what was run; IntRate varies per job, Comment describes one upload, Hash is derived,
# OutputDir only says where the data is (a production may have several) and MasterJobID orders the writers
CONTENT_FIELDS = ("Col", "OrbitsPerTF", "McTag", "RecoTag", "FirstOrbitMC")

def publishing_disabled():
   """
   True if the job environment opts out of publishing MCProdInfo (e.g. validation jobs reusing a production tag)
   """
   return os.getenv("ALIEN_JDL_DISABLE_MCPRODINFO", "") not in ("", "0")

def _normalised(value):
   # values read back from CCDB may differ in type (e.g. 27020420 vs 27020420.0) or be empty
   if value == None or value == "":
     return None
   try:
     return float(value)
   except (TypeError, ValueError):
     return str(value)

def _masterjob(info):
   # MasterJobID as int; a non-numeric value counts as absent
   value = info.MasterJobID
   if value == None or value == "":
     return None
   try:
     return int(value)
   except (TypeError, ValueError):
     print(f"WARNING: ignoring non-numeric MasterJobID {value} of MCProdInfo {info.LPMProductionTag} run {info.RunNumber}")
     return None

def changed_content(stored, new, complete=False):
   """
   Content fields where the new object differs from the stored one, as {field: (old, new)}.
   Unless complete, a field the new object leaves empty is unknown and not a change.
   """
   return {f: (getattr(stored, f), getattr(new, f)) for f in CONTENT_FIELDS
           if (complete or _normalised(getattr(new, f)) != None)
           and _normalised(getattr(new, f)) != _normalised(getattr(stored, f))}

def is_stale_writer(stored, new):
   """
   True if the new object may not replace the stored one because it comes from an older (or unknown) masterjob.
   Objects without MasterJobID (old ones) can be replaced by any writer.
   """
   stored_key, new_key = _masterjob(stored), _masterjob(new)
   if stored_key == None:
     return False
   return new_key == None or new_key < stored_key

def publish_MCProdInfo(mc_prod_info, ccdb_url = "https://alice-ccdb.cern.ch", username = "aliprod", force_overwrite=False,
                       complete=False, include_meta_into_aod=False):
   """
   Publishes mc_prod_info for its tag and run.
   - no stored object: uploads it.
   - complete=True (a GRID job that knows all fields): an empty field counts as a value; a differing content
     is uploaded as a new version with a warning, unless the stored one comes from a newer masterjob or this
     job has no production OutputDir. A FirstOrbitMC that differs while all else is equal keeps the stored value.
   - complete=False (offline tools): only fills fields that are empty in the stored object, and nothing at all
     if a content field conflicts.
   - force_overwrite: uploads in any case; fields left empty keep their stored values.
   Returns the response of the upload or None.
   """
   print("Publishing MCProdInfo")

   if mc_prod_info.LPMProductionTag == None or len(mc_prod_info.LPMProductionTag) == 0:
       print ("No LPM production tag found; Not publishing")
       return

   try:
     mc_prod_info_q, stored_raw = query_mcprodinfo(ccdb_url, username, mc_prod_info.RunNumber, mc_prod_info.LPMProductionTag, raw=True)
   except (RuntimeError, requests.RequestException) as e:
     print(f"WARNING: Not publishing MCProdInfo, the existing one could not be read: {e}")
     return None

   def upload(info, raw = {}, retry = True):
     # raw: stored metadata strings that are uploaded unchanged
     def post(info, raw):
       keys = dataclasses.asdict(info)
       keys.update({k: v for k, v in raw.items() if k in keys and k != "Hash"})
       try:
         return upload_mcprodinfo_meta(ccdb_url, username, info.RunNumber, info.LPMProductionTag, keys)
       except requests.RequestException as e:
         print(f"WARNING: upload of MCProdInfo failed: {e}")
         return None
     r = post(info, raw)
     if retry and (r == None or not 200 <= r.status_code < 300) and info.OutputDir != None:
       # a rejected OutputDir must not lose the whole object
       print("WARNING: retrying the upload of MCProdInfo without OutputDir")
       r = post(dataclasses.replace(info, OutputDir = None, Hash = None), {k: v for k, v in raw.items() if k != "OutputDir"})
     return r

   def summary(changes):
     return ", ".join(f"{f}: {old} -> {new}" for f, (old, new) in changes.items())

   def merged(info):
     # optional fields this writer leaves empty keep their stored values
     kept = {f.name: getattr(mc_prod_info_q, f.name) for f in fields(MCProdInfo)
             if f.name != "Hash" and f.default is not dataclasses.MISSING
             and getattr(info, f.name) == None and getattr(mc_prod_info_q, f.name) != None}
     return dataclasses.replace(info, Hash = None, **kept) if kept else info

   if mc_prod_info_q == None:
     return upload(mc_prod_info)

   where = f"MCProdInfo of {mc_prod_info.LPMProductionTag} run {mc_prod_info.RunNumber}"
   if force_overwrite:
     print(f"{where}: uploading (forced)")
     return upload(merged(mc_prod_info))

   changes = changed_content(mc_prod_info_q, mc_prod_info, complete)
   # values that replace stored ones; filling an empty field is not a replacement
   replaced = {f: c for f, c in changes.items() if c[0] != None}
   added = {f: c for f, c in changes.items() if c[0] == None}

   if replaced and not complete:
     print(f"WARNING: {where} differs from the stored one; not changing it without force_overwrite ({summary(replaced)})")
     return None

   if set(replaced) == {"FirstOrbitMC"}:
     # a stored first orbit describes the data already produced by this software
     old, new = replaced["FirstOrbitMC"]
     print(f"WARNING: {where} has FirstOrbitMC {old}, this job uses {new}; "
           f"its timeframes will be misaligned in analysis. Keeping the stored value")
     replaced = {}

   if replaced:
     if mc_prod_info.OutputDir == None:
       print(f"WARNING: {where} differs from the stored one, but this job writes outside of a production directory; "
             f"not replacing it ({summary(replaced)})")
       return None
     # a writer with a production directory may replace an object written outside of one (e.g. by a validation job)
     if mc_prod_info_q.OutputDir != None and is_stale_writer(mc_prod_info_q, mc_prod_info):
       print(f"WARNING: {where} was written by masterjob {mc_prod_info_q.MasterJobID}; this job's masterjob "
             f"{mc_prod_info.MasterJobID} is older or unknown, so not replacing it ({summary(replaced)})")
       return None
     print(f"WARNING: {where} differs from the stored one; uploading a new version ({summary(replaced)})")
     return upload(mc_prod_info)

   # same production: fill the empty fields and keep all stored values
   fills = dict(added)
   if mc_prod_info_q.OutputDir == None and mc_prod_info.OutputDir != None:
     fills["OutputDir"] = (None, mc_prod_info.OutputDir)
   stored_key, new_key = _masterjob(mc_prod_info_q), _masterjob(mc_prod_info)
   if new_key != None and (stored_key == None or (complete and fills and new_key > stored_key)):
     fills["MasterJobID"] = (mc_prod_info_q.MasterJobID, new_key)
   if not fills:
     print(f"{where} is up to date; not publishing")
     return None
   if stored_key != None and new_key != None and new_key < stored_key:
     print(f"WARNING: {where} was written by a newer masterjob {stored_key}; not filling {summary(fills)}")
     return None
   print(f"{where}: filling {summary(fills)}")
   filled = dataclasses.replace(mc_prod_info_q, Hash = None, **{f: new for f, (_, new) in fills.items()})
   # without anything else to fill, a rejected OutputDir is not retried; it would only duplicate the stored version
   return upload(filled, {k: v for k, v in stored_raw.items() if k not in fills}, retry = set(fills) != {"OutputDir"})
