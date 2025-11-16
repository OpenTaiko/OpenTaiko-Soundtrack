import os
from collections import defaultdict


def parse_tja_levels(tja_file_path):
    """Parse a .tja file and extract LEVEL values for Oni and Edit courses."""
    levels = {}
    
    try:
        with open(tja_file_path, "r", encoding="utf-8-sig", errors="ignore") as tja_file:
            current_course = None

            for line in tja_file:
                line = line.strip()
                
                if line.startswith("COURSE:"):
                    current_course = line.split("COURSE:", 1)[1].strip()
                
                elif line.startswith("LEVEL:"):
                    level_value = line.split("LEVEL:", 1)[1].strip()
                    
                    # Only track Oni (3/Oni) and Edit (4/Edit) courses
                    if current_course in ["3", "Oni", "4", "Edit"]:
                        # Normalize course to standard name
                        course_key = "Oni" if current_course in ["3", "Oni"] else "Edit"
                        
                        # Try to parse as float if it contains decimal, otherwise int
                        if '.' in level_value:
                            try:
                                levels[course_key] = float(level_value)
                            except ValueError:
                                print(f"Invalid LEVEL format in {tja_file_path}: {level_value}")
                        else:
                            try:
                                levels[course_key] = int(level_value)
                            except ValueError:
                                print(f"Invalid LEVEL format in {tja_file_path}: {level_value}")
    
    except Exception as e:
        print(f"Error parsing {tja_file_path}: {e}")
    
    return levels


def count_levels(base_path):
    """Scan all .tja files and count LEVEL occurrences for Oni and Edit."""
    oni_levels = defaultdict(int)  # For course 3/Oni
    edit_levels = defaultdict(int)  # For course 4/Edit
    
    for root, _, files in os.walk(base_path):
        # Skip Replay folders
        if "Replay" in root:
            continue
        
        for file in files:
            if file.endswith(".tja"):
                tja_file_path = os.path.join(root, file)
                levels = parse_tja_levels(tja_file_path)
                
                # Count levels by course
                if "Oni" in levels:
                    oni_levels[levels["Oni"]] += 1
                if "Edit" in levels:
                    edit_levels[levels["Edit"]] += 1
    
    return oni_levels, edit_levels


def print_results(oni_levels, edit_levels):
    """Print formatted results of level counts."""
    print("\n" + "="*50)
    print("ONI (Course 3/Oni) LEVEL Distribution")
    print("="*50)
    
    if oni_levels:
        for level in sorted(oni_levels.keys()):
            print(f"Level {level}: {oni_levels[level]} charts")
        print(f"\nTotal Oni charts: {sum(oni_levels.values())}")
    else:
        print("No Oni charts found.")
    
    print("\n" + "="*50)
    print("EDIT (Course 4/Edit) LEVEL Distribution")
    print("="*50)
    
    if edit_levels:
        for level in sorted(edit_levels.keys()):
            print(f"Level {level}: {edit_levels[level]} charts")
        print(f"\nTotal Edit charts: {sum(edit_levels.values())}")
    else:
        print("No Edit charts found.")
    
    print("\n" + "="*50)
    print("COMBINED (Oni + Edit) LEVEL Distribution")
    print("="*50)
    
    # Combine both dictionaries
    combined_levels = defaultdict(int)
    for level, count in oni_levels.items():
        combined_levels[level] += count
    for level, count in edit_levels.items():
        combined_levels[level] += count
    
    if combined_levels:
        for level in sorted(combined_levels.keys()):
            print(f"Level {level}: {combined_levels[level]} charts")
        print(f"\nTotal Combined charts: {sum(combined_levels.values())}")
    else:
        print("No charts found.")
    
    print("\n" + "="*50)


if __name__ == "__main__":
    base_directory = os.getcwd()  # Current directory
    
    print(f"Scanning .tja files in: {base_directory}")
    oni_levels, edit_levels = count_levels(base_directory)
    print_results(oni_levels, edit_levels)