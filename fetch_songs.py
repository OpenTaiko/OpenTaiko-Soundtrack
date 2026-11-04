from pydub import AudioSegment
import os
import json
import hashlib
import re
import chardet

# Matches localized header tags such as TITLEJA / SUBTITLEZH, but not plain TITLE: / SUBTITLE:
LOCALIZED_TAG = re.compile(r"^(TITLE|SUBTITLE)([A-Z]{2,3}(?:_[A-Z]{2,})*):(.*)$")

# Chart files: .tja and .optktci hold charts; .optktcm (dan) and .optktct (tower) reference other songs by id
CHART_FILES = (".tja", ".tci", ".optktci")
REFERENCE_FILES = (".tcm", ".optktcm", ".tct", ".optktct")

# Course names as the catalog writes them, by OpenTaiko's difficulty index
COURSE_NAMES = ["Easy", "Normal", "Hard", "Oni", "Edit", "Tower", "Dan"]
COURSE_INDEX = {"easy": 0, "normal": 1, "hard": 2, "oni": 3, "edit": 4, "ura": 4, "tower": 5, "dan": 6}


def course_index(name):
    name = str(name).strip().lower()
    if name.isdigit():
        return int(name)
    return COURSE_INDEX.get(name, -1)


def read_json(file_path):
    with open(file_path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def localized(token):
    # A JSON chart's title is a string or {lang: text}: the default text, and the other languages keyed
    # like the .tja tags (JA, ZH_TW...)
    if isinstance(token, dict):
        default = token.get("default") or next(iter(token.values()), "")
        return default, {k.upper(): v for k, v in token.items() if k != "default"}
    return (token or ""), {}


def as_text(token):
    if isinstance(token, list):
        return ", ".join(str(t) for t in token)
    return token or ""


def read_unique_id(folder, chart_file_path):
    unique_id_file = os.path.join(folder, "uniqueID.json")
    if not os.path.exists(unique_id_file):
        return "Unknown"
    try:
        return read_json(unique_id_file).get("id", "")
    except Exception as e:
        print(f"Error reading uniqueId.json in {chart_file_path}: {e}")
        return "Unknown"


def create_audio_preview(file_path, name, start_sec):
    # Get original file extension
    _, ext = os.path.splitext(file_path)
    ext = ext.lower().lstrip('.')  # e.g., "mp3", "wav"

    # Ensure output path keeps the original extension
    output_filename = f"{name}.{ext}"
    output_path = os.path.join("preview", output_filename)

    # If the preview already exists, skip and return the path
    if os.path.exists(output_path):
        print(f"Preview already exists at {output_path}. Skipping.")
        return output_path

    # Ensure preview directory exists
    os.makedirs("preview", exist_ok=True)

    # Load and slice audio
    audio = AudioSegment.from_file(file_path)
    start_ms = int(float(start_sec) * 1000)
    end_ms = min(len(audio), start_ms + 15000)
    preview = audio[start_ms:end_ms]

    # Export preview
    preview.export(output_path, format=ext)
    print(f"Preview saved to {output_path}")

    return output_path

# Function to detect file encoding
def detect_encoding(file_path):
    with open(file_path, "rb") as f:
        raw_data = f.read(4096)  # Read a chunk to detect encoding
    result = chardet.detect(raw_data)
    return result['encoding']

# Function to calculate the MD5 checksum of a file
def calculate_md5(file_path, encoding):
    try:
        with open(file_path, 'rb') as f:
            data = f.read()    
            return hashlib.md5(data).hexdigest()
    except Exception as e:
        print(f"Error calculating MD5 for {file_path}: {e}")
        return None

# Function to find all files within a folder while ignoring "Replay" folders
def find_files(folder):
    file_paths = []
    for root, _, files in os.walk(folder):
        # Ignore "Replay" folders
        if "Replay" in root:
            continue
        for file in files:
            file_paths.append(os.path.join(root, file))
    return file_paths

# Function to calculate the total size of files in bytes
def calculate_total_size(file_paths):
    total_size = 0
    for file_path in file_paths:
        total_size += os.path.getsize(file_path)
    return total_size / (1024 * 1024)  # Convert bytes to megabytes

# Function to parse .tja files and extract metadata
def parse_tja_file(tja_file_path, base_path):
    chart_title = ""
    chart_subtitle = ""
    chart_titles = {}
    chart_subtitles = {}
    chart_audio_file = ""
    chart_jacket_file = ""
    chart_maker = ""
    chart_difficulties = {}
    chart_notesdesigner = {}
    chart_demostart = 0
    
    try:
        with open(tja_file_path, "r", encoding="utf-8-sig", errors="ignore") as tja_file:
            current_course = None
            current_level = None

            for line in tja_file:
                line = line.strip()
                
                if line.startswith("TITLE:"):
                    chart_title = line.split("TITLE:", 1)[1].strip()
                elif line.startswith("SUBTITLE:"):
                    chart_subtitle = line.split("SUBTITLE:", 1)[1].strip()
                    # Remove "--" or "++" at the start of SUBTITLE
                    if chart_subtitle.startswith("--") or chart_subtitle.startswith("++"):
                        chart_subtitle = chart_subtitle[2:].strip()
                elif LOCALIZED_TAG.match(line):
                    tag, lang, value = LOCALIZED_TAG.match(line).groups()
                    value = value.strip()
                    if tag == "SUBTITLE":
                        # Same "--"/"++" convention as the plain SUBTITLE tag
                        if value.startswith("--") or value.startswith("++"):
                            value = value[2:].strip()
                        chart_subtitles[lang] = value
                    else:
                        chart_titles[lang] = value
                elif line.startswith("WAVE:"):
                    chart_audio_file = line.split("WAVE:", 1)[1].strip()
                elif line.startswith("PREIMAGE:"):
                    chart_jacket_file = line.split("PREIMAGE:", 1)[1].strip()
                elif line.startswith("MAKER:"):
                    chart_maker = line.split("MAKER:", 1)[1].strip()
                elif line.startswith("DEMOSTART:"):
                    chart_demostart = line.split("DEMOSTART:", 1)[1].strip()
                elif line.startswith("COURSE:"):
                    current_course = line.split("COURSE:", 1)[1].strip()
                elif line.startswith("NOTESDESIGNER"):
                    ndvalue = line.split(":", 1)[1].strip()
                    if current_course is not None:
                        chart_notesdesigner[current_course] = ndvalue
                elif line.startswith("LEVEL:"):
                    # Check if LEVEL contains a decimal point
                    level_value = line.split("LEVEL:", 1)[1].strip()
                    if '.' in level_value:
                        try:
                            current_level = float(level_value)
                        except ValueError:
                            print(f"Invalid LEVEL format (float) in {tja_file_path} for line: {line}")
                    else:
                        try:
                            current_level = int(level_value)
                        except ValueError:
                            print(f"Invalid LEVEL format (int) in {tja_file_path} for line: {line}")
                    
                    if current_course and current_level is not None:
                        chart_difficulties[current_course] = current_level

    except Exception as e:
        print(f"Error parsing {tja_file_path}: {e}")
    
    tja_folder = os.path.relpath(os.path.dirname(tja_file_path), base_path)
    chart_audio_file_path = os.path.join(tja_folder, chart_audio_file) if chart_audio_file else None
    chart_jacket_file_path = os.path.join(tja_folder, chart_jacket_file) if chart_jacket_file else None
    
    # Set MAKER for all missing NOTESDESIGNER
    for key in chart_difficulties:
        if key not in chart_notesdesigner:
            chart_notesdesigner[key] = chart_maker

    return {
        "chartTitle": chart_title,
        "chartTitles": chart_titles,
        "chartSubtitle": chart_subtitle,
        "chartSubtitles": chart_subtitles,
        "chartDifficulties": chart_difficulties,
        "chartAudioFilePath": chart_audio_file_path,
        "chartJacketFilePath": chart_jacket_file_path,
        "chartMakers": chart_notesdesigner,
        "chartDemoStart": chart_demostart
    }

# Function to parse .optktci files (JSON charts with osu! courses) and extract metadata
def parse_tci_file(tci_file_path, base_path):
    try:
        tci = read_json(tci_file_path)
    except Exception as e:
        print(f"Error parsing {tci_file_path}: {e}")
        tci = {}
    title, titles = localized(tci.get("title"))
    subtitle, subtitles = localized(tci.get("subtitle"))
    maker = as_text(tci.get("creator"))
    difficulties, makers = {}, {}
    for course in tci.get("courses") or []:
        index = course_index(course.get("difficulty", ""))
        if 0 <= index < len(COURSE_NAMES):
            level = course.get("level", 0)
            difficulties[COURSE_NAMES[index]] = int(level) if float(level).is_integer() else level
            makers[COURSE_NAMES[index]] = maker
    folder = os.path.relpath(os.path.dirname(tci_file_path), base_path)
    return {
        "chartTitle": title,
        "chartTitles": titles,
        "chartSubtitle": subtitle,
        "chartSubtitles": subtitles,
        "chartDifficulties": difficulties,
        "chartAudioFilePath": os.path.join(folder, tci["audio"]) if tci.get("audio") else None,
        "chartJacketFilePath": os.path.join(folder, tci["albumart"]) if tci.get("albumart") else None,
        "chartMakers": makers,
        "chartDemoStart": tci.get("songpreview", 0)
    }


# The course of a referenced song as a catalog entry stores it: (level, maker), or None when missing
def referenced_course(song, difficulty):
    index = course_index(difficulty or "oni")
    for name, level in song["chartDifficulties"].items():
        if course_index(name) == index:
            return level, song["chartMakers"].get(name, "")
    return None


# Function to build the metadata of an .optktcm (dan) or .optktct (tower) file from the songs it references;
# songs = the parsed charts by unique id
def parse_reference_file(file_path, base_path, songs):
    data = read_json(file_path)
    is_dan = file_path.lower().endswith((".tcm", ".optktcm"))
    refs = (data.get("charts") or []) if is_dan else [data]
    missing = [r.get("id") for r in refs if r.get("id") not in songs]
    if missing or not refs:
        print(f"Skipping {file_path}: references songs that are not in the soundtrack ({missing})")
        return None
    first = songs[refs[0]["id"]]
    title, titles = localized(data.get("title")) if data.get("title") is not None else (first["chartTitle"], first["chartTitles"])
    subtitle, subtitles = localized(data.get("subtitle")) if data.get("subtitle") is not None else (first["chartSubtitle"], first["chartSubtitles"])
    makers = []
    for r in refs:
        course = referenced_course(songs[r["id"]], r.get("difficulty"))
        if course is None:
            print(f"Skipping {file_path}: song {r['id']} has no {r.get('difficulty')} course")
            return None
        if course[1] and course[1] not in makers:
            makers.append(course[1])
    if is_dan:
        # an .optktcm may set the dan's own level; without one (and in a plain .tcm) the game shows level 10
        level = data.get("level") if file_path.lower().endswith(".optktcm") else None
        if level is None or float(level) < 0:
            level = 10
        difficulties = {"Dan": int(level) if float(level).is_integer() else level}
        maker_by_course = {"Dan": ", ".join(makers)}
        jacket = os.path.join(os.path.relpath(os.path.dirname(file_path), base_path), data["albumart"]) if data.get("albumart") else None
    else:
        level = data.get("level")
        if level is None:
            level = referenced_course(first, data.get("difficulty"))[0]
        difficulties = {"Tower": int(level) if float(level).is_integer() else level}
        maker_by_course = {"Tower": makers[0] if makers else ""}
        jacket = first["chartJacketFilePath"]
    return {
        "chartTitle": title,
        "chartTitles": titles,
        "chartSubtitle": subtitle,
        "chartSubtitles": subtitles,
        "chartDifficulties": difficulties,
        # the preview is the first referenced song's own (the tower's song for a tower)
        "previewPath": first["previewPath"],
        "chartJacketFilePath": jacket,
        "chartMakers": maker_by_course,
        # the songs it plays, to download with it
        "chartDependencies": list(dict.fromkeys(r["id"] for r in refs))
    }


# Function to generate the JSON data for each chart file (.tja, .optktci, then the .optktcm/.optktct
# referencing them)
def process_tja_files(base_path):
    data = []
    songs = {}          # parsed .tja/.optktci metadata by unique id, for the files referencing them
    references = []

    for root, _, files in os.walk(base_path):
        if "Replay" in root:
            continue  # Skip any directory path containing "Replay"

        for file in files:
            if file.lower().endswith(REFERENCE_FILES):
                references.append((root, file))
            elif file.lower().endswith(CHART_FILES):
                chart_file_path = os.path.join(root, file)
                if file.lower().endswith(".tja"):
                    metadata = parse_tja_file(chart_file_path, base_path)
                else:
                    metadata = parse_tci_file(chart_file_path, base_path)
                entry = make_entry(base_path, root, chart_file_path, metadata)
                if entry is not None:
                    data.append(entry)
                    songs[entry["uniqueId"]] = dict(metadata, previewPath=entry["chartAudioFilePath"])

    # dans and towers last: their metadata comes from the songs they reference
    for root, file in references:
        chart_file_path = os.path.join(root, file)
        try:
            metadata = parse_reference_file(chart_file_path, base_path, songs)
        except Exception as e:
            print(f"Error parsing {chart_file_path}: {e}")
            continue
        if metadata is not None:
            entry = make_entry(base_path, root, chart_file_path, metadata)
            if entry is not None:
                data.append(entry)

    return data


# One catalog entry for a chart file and its folder, None when the file can't be read
def make_entry(base_path, root, chart_file_path, metadata):
    sub_genre_folder = os.path.basename(os.path.dirname(root))

    # Find all files within the chart's folder
    folder_files = find_files(root)
    files_paths = [os.path.relpath(file, base_path) for file in folder_files]

    # Detect file encoding and compute MD5 checksum
    try:
        encoding = detect_encoding(chart_file_path)
        chart_md5 = calculate_md5(chart_file_path, encoding)
    except Exception as e:
        print(f"Skipping {chart_file_path} due to encoding detection failure: {e}")
        return None

    if chart_md5 is None:
        print(f"Skipping {chart_file_path} due to MD5 calculation failure.")
        return None

    # Calculate total size of all files in the chart's folder
    total_size_mb = calculate_total_size(folder_files)

    # Get uniqueId from uniqueId.json using utf-8-sig encoding to handle BOM
    unique_id = read_unique_id(root, chart_file_path)

    # Create preview if does not exist; a dan or tower uses the preview of the song it references
    if metadata.get("previewPath"):
        preview_path = metadata["previewPath"]
    else:
        preview_path = create_audio_preview(metadata.get("chartAudioFilePath"), unique_id, metadata.get("chartDemoStart"))

    entry = {
        "uniqueId": unique_id,
        "tjaFolderPath": os.path.relpath(root, base_path),
        "tjaFilesPath": files_paths,
        "tjaGenreFolder": sub_genre_folder,
        "tjaMD5": chart_md5,
        # Size in MB, rounded to 3 decimal places; a folder of a few bytes (a dan or tower referencing other
        # songs) still shows 0.001, never 0
        "chartSize": max(round(total_size_mb, 3), 0.001) if total_size_mb > 0 else 0.0,
        "chartTitle": metadata.get("chartTitle"),
        "chartTitles": metadata.get("chartTitles"),
        "chartSubtitle": metadata.get("chartSubtitle"),
        "chartSubtitles": metadata.get("chartSubtitles"),
        "chartDifficulties": metadata.get("chartDifficulties"),
        "chartMakers": metadata.get("chartMakers"),
        "chartAudioFilePath": preview_path,
        "chartJacketFilePath": metadata.get("chartJacketFilePath")
    }
    # an extra after the usual fields: dans and towers list the songs they play
    if metadata.get("chartDependencies"):
        entry["chartDependencies"] = metadata["chartDependencies"]
    return entry

# Main function to create the JSON output
def create_tja_json(base_path, output_file):
    tja_data = process_tja_files(base_path)
    
    hof_append = {}
    with open('hof.json', 'r') as file:
        hof_append = json.load(file)
        for item in tja_data:
            unique_id = item["uniqueId"]
            item["chartHoFRanks"] = hof_append.get(unique_id, {})
    
    with open(output_file, "w", encoding="utf-8") as json_file:
        json.dump(tja_data, json_file, indent=4)
        
if __name__ == "__main__":
    base_directory = os.getcwd()  # You can replace this with any directory path
    output_json_file = "soundtrack_info.json"
    create_tja_json(base_directory, output_json_file)
    print(f"JSON file '{output_json_file}' created successfully.")
