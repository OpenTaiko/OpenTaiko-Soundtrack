from pydub import AudioSegment
import os
import json
import hashlib
import chardet


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
        "chartSubtitle": chart_subtitle,
        "chartDifficulties": chart_difficulties,
        "chartAudioFilePath": chart_audio_file_path,
        "chartJacketFilePath": chart_jacket_file_path,
        "chartMakers": chart_notesdesigner,
        "chartDemoStart": chart_demostart
    }

# Function to generate the JSON data for each .tja file
def process_tja_files(base_path):
    data = []

    for root, _, files in os.walk(base_path):
        if "Replay" in root:
            continue  # Skip any directory path containing "Replay"
        
        for file in files:
            if file.endswith(".tja"):
                tja_file_path = os.path.join(root, file)
                tja_folder = os.path.basename(root)
                sub_genre_folder = os.path.basename(os.path.dirname(root))
                
                # Find all files within the TjaFolder
                tja_folder_files = find_files(root)
                tja_files_paths = [os.path.relpath(file, base_path) for file in tja_folder_files]
                
                # Detect file encoding and compute MD5 checksum
                try:
                    encoding = detect_encoding(tja_file_path)
                    tja_md5 = calculate_md5(tja_file_path, encoding)
                except Exception as e:
                    print(f"Skipping {tja_file_path} due to encoding detection failure: {e}")
                    continue

                if tja_md5 is None:
                    print(f"Skipping {tja_file_path} due to MD5 calculation failure.")
                    continue

                # Calculate total size of all files in the TjaFolder
                total_size_mb = calculate_total_size(tja_folder_files)

                # Get uniqueId from uniqueId.json using utf-8-sig encoding to handle BOM
                unique_id_file = os.path.join(root, "uniqueID.json")
                if os.path.exists(unique_id_file):
                    try:
                        with open(unique_id_file, "r", encoding="utf-8-sig") as uid_file:
                            unique_id_data = json.load(uid_file)
                            unique_id = unique_id_data.get("id", "")
                    except Exception as e:
                        print(f"Error reading uniqueId.json in {tja_file_path}: {e}")
                        unique_id = "Unknown"
                else:
                    unique_id = "Unknown"
                
                # Parse .tja file for metadata
                tja_metadata = parse_tja_file(tja_file_path, base_path)
                
                # Create preview if does not exist
                preview_path = create_audio_preview(tja_metadata.get("chartAudioFilePath"), unique_id, tja_metadata.get("chartDemoStart"))

                # Add the tja file data to the list
                data.append({
                    "uniqueId": unique_id,
                    "tjaFolderPath": os.path.relpath(root, base_path),
                    "tjaFilesPath": tja_files_paths,
                    "tjaGenreFolder": sub_genre_folder,
                    "tjaMD5": tja_md5,
                    "chartSize": round(total_size_mb, 2),  # Size in MB, rounded to 2 decimal places
                    "chartTitle": tja_metadata.get("chartTitle"),
                    "chartSubtitle": tja_metadata.get("chartSubtitle"),
                    "chartDifficulties": tja_metadata.get("chartDifficulties"),
                    "chartMakers": tja_metadata.get("chartMakers"),
                    "chartAudioFilePath": preview_path,
                    "chartJacketFilePath": tja_metadata.get("chartJacketFilePath")
                })

    return data

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
