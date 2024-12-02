from pybtex.database.input import bibtex
import string

# Open the bibtex file with the correct encoding
bib_file_path = r"C:\Users\dlaa0001\Documents\PhD\review_paper\data\raw\ref.bib"
cleaned_bib_file_path = r"C:\Users\dlaa0001\Documents\PhD\review_paper\data\raw\cleaned_ref.bib"

try:
    with open(bib_file_path, "r", encoding="utf-8") as file:
        lines = file.readlines()
except UnicodeDecodeError:
    # Retry with a more permissive encoding
    with open(bib_file_path, "r", encoding="latin-1", errors="replace") as file:
        lines = file.readlines()

# Remove duplicates
unique_entries = {}
current_entry_key = None
filtered_bibtex = []
for line in lines:
    if line.startswith("@"):
        entry_key = line.split("{", 1)[1].split(",", 1)[0].strip()
        if entry_key in unique_entries:
            current_entry_key = None  # Ignore duplicate entries
            continue
        unique_entries[entry_key] = True
        current_entry_key = entry_key
    if current_entry_key is not None:
        filtered_bibtex.append(line)

# Write a cleaned version of the .bib file
with open(cleaned_bib_file_path, "w", encoding="utf-8") as clean_file:
    clean_file.writelines(filtered_bibtex)

# Parse the cleaned .bib file
parser = bibtex.Parser()
bibdata = parser.parse_file(cleaned_bib_file_path)

# Translator for removing punctuation
translator = str.maketrans('', '', string.punctuation)

# Open the output file
output_csv_path = r'C:\Users\dlaa0001\Documents\PhD\review_paper\data\raw\my_bib.csv'
with open(output_csv_path, 'w', encoding="utf-8") as f:
    # Header row
    f.write("title,year,author,journal\n")

    # Loop through the individual references
    for bib_id in bibdata.entries:
        b = bibdata.entries[bib_id].fields
        try:
            # Write entry to CSV
            f.write('"')
            f.write(b["title"].replace('"', '""'))  # Escape double quotes
            f.write('"')
            f.write(",")
            f.write(b["year"])
            f.write(",")
            
            # Deal with multiple authors
            authors = ""
            for author in bibdata.entries[bib_id].persons.get("author", []):
                new_author = str(author.first_names) + " " + str(author.last_names)
                new_author = new_author.translate(translator)
                if not authors:
                    authors = '"' + new_author
                else:
                    authors += "; " + new_author
            authors += '"' if authors else '""'
            f.write(authors)
            f.write(",")
            f.write('"')
            f.write(b.get("journal", "").replace('"', '""'))  # Escape double quotes
            f.write('"')
        except KeyError:
            # Skip incomplete entries
            continue
        
        f.write("\n")
