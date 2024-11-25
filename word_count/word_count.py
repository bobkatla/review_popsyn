import os
import sys
import PyPDF2
from collections import Counter
import spacy
import polars as pl


def extract_text_from_pdf(pdf_path):
    """Extract text from a PDF file."""
    pdf_text = ""
    with open(pdf_path, 'rb') as pdf_file:
        reader = PyPDF2.PdfReader(pdf_file)
        for page in reader.pages:
            pdf_text += page.extract_text()
    return pdf_text


def is_heading_or_title(line):
    """Detect if a line is likely a heading or title."""
    # Exclude lines that are short (likely headings/titles)
    if len(line) < 50:
        return True
    # Exclude lines that are in ALL CAPS (likely titles)
    if line.isupper():
        return True
    # Exclude lines that are mostly capitalized (titles/headings)
    if sum(1 for c in line if c.isupper()) > 0.6 * len(line):
        return True
    return False


def filter_main_content(text):
    """Filter out likely headers, titles, and headings."""
    lines = text.split("\n")
    content_lines = [line for line in lines if not is_heading_or_title(line.strip())]
    return "\n".join(content_lines)


def count_words_and_complex_nouns(text):
    """Count individual words, normal complex nouns, and two-word complex nouns."""
    nlp = spacy.load("en_core_web_sm")
    doc = nlp(text)

    # Define stop words and filter criteria
    stop_words = nlp.Defaults.stop_words
    insignificant_words = set(stop_words)
    insignificant_words.update(["such as", "etc", "e.g.", "bhat", "et", "al", "mckay", "farooq", "müller", "guo", "ma", "nagel", "bierlaire", "miller", "axhausen", "beckman", "timmermans", "baggerly"])  # Add custom phrases
    insignificant_words = {word.lower() for word in insignificant_words}

    # Helper function to check if a noun chunk contains stop words
    def contains_stop_words(chunk):
        words_in_chunk = chunk.text.lower().split()
        return any(word in insignificant_words for word in words_in_chunk)

    # Extract words and filter out stop words, numbers, and single-letter words
    words = [
        token.text.lower()
        for token in doc
        if token.is_alpha
        and len(token.text) > 1  # Exclude single-letter words
        and token.text.lower() not in insignificant_words
    ]

    # Extract all complex nouns (including those with numbers) and exclude ones containing stop words
    normal_complex_nouns = [
        " ".join(chunk.text.lower().split())
        for chunk in doc.noun_chunks
        if len(chunk.text.split()) > 1  # Include any length of noun chunks
        and not contains_stop_words(chunk)  # Exclude complex nouns with stop words
    ]

    # Extract exactly two-word complex nouns (excluding numbers) and exclude ones containing stop words
    def contains_number(chunk):
        return any(word.isdigit() for word in chunk.text.split())

    two_word_complex_nouns = [
        " ".join(chunk.text.lower().split())
        for chunk in doc.noun_chunks
        if len(chunk.text.split()) == 2  # Only include exactly two words
        and not contains_number(chunk)
        and not contains_stop_words(chunk)  # Exclude two-word complex nouns with stop words
    ]

    # Count occurrences
    word_count = Counter(words)
    normal_complex_noun_count = Counter(normal_complex_nouns)
    two_word_complex_noun_count = Counter(two_word_complex_nouns)

    return word_count, normal_complex_noun_count, two_word_complex_noun_count


def process_folder(folder_path):
    """Process all PDF files in a folder and return term counts."""
    word_counts = {}
    normal_complex_noun_counts = {}
    two_word_complex_noun_counts = {}
    all_terms = set()  # Store all unique terms (words, normal complex nouns, and two-word complex nouns)

    # Process each PDF file
    for file_name in os.listdir(folder_path):
        if file_name.endswith(".pdf"):
            file_path = os.path.join(folder_path, file_name)
            print(f"Processing file: {file_path}")

            # Extract and filter text
            text = extract_text_from_pdf(file_path)
            filtered_text = filter_main_content(text)

            # Count words, normal complex nouns, and two-word complex nouns
            word_count, normal_complex_noun_count, two_word_complex_noun_count = count_words_and_complex_nouns(
                filtered_text
            )
            word_counts[file_path] = word_count
            normal_complex_noun_counts[file_path] = normal_complex_noun_count
            two_word_complex_noun_counts[file_path] = two_word_complex_noun_count

            # Combine all unique terms
            all_terms.update(word_count.keys())
            all_terms.update(normal_complex_noun_count.keys())
            all_terms.update(two_word_complex_noun_count.keys())

    return word_counts, normal_complex_noun_counts, two_word_complex_noun_counts, all_terms


def process_with_optional_subtract(main_folder, subtract_folder=None, threshold=5):
    """Process the main folder and optionally subtract terms from the subtract folder."""
    # Process main folder
    (
        word_counts_main,
        normal_complex_noun_counts_main,
        two_word_complex_noun_counts_main,
        all_terms_main,
    ) = process_folder(main_folder)

    # Initialize variables for subtract folder processing
    subtract_term_frequencies = {}

    if subtract_folder and os.path.isdir(subtract_folder):
        print(f"\nProcessing subtract folder: {subtract_folder}")
        (
            word_counts_subtract,
            normal_complex_noun_counts_subtract,
            two_word_complex_noun_counts_subtract,
            all_terms_subtract,
        ) = process_folder(subtract_folder)

        # Combine counts for all terms in the subtract folder
        subtract_term_frequencies = {term: 0 for term in all_terms_subtract}
        for file_path in word_counts_subtract.keys():
            for term in all_terms_subtract:
                count = (
                    word_counts_subtract[file_path].get(term, 0)
                    + normal_complex_noun_counts_subtract[file_path].get(term, 0)
                    + two_word_complex_noun_counts_subtract[file_path].get(term, 0)
                )
                subtract_term_frequencies[term] += count

    # Filter terms from the subtract folder if provided and threshold applies
    if subtract_folder and subtract_term_frequencies:
        accepted_terms = {
            term
            for term, freq in subtract_term_frequencies.items()
            if freq <= threshold
        }
    else:
        accepted_terms = all_terms_main

    # Retain only terms from the main folder that are not excluded by the subtract folder
    final_terms = all_terms_main.intersection(accepted_terms)

    # Filter terms to only include those that appear in at least 50% of the main folder's files
    num_files_main = len(word_counts_main)
    threshold_main = num_files_main / 2

    term_presence = {term: 0 for term in final_terms}
    term_frequencies = {term: 0 for term in final_terms}

    for file_path in word_counts_main.keys():
        for term in final_terms:
            count = (
                word_counts_main[file_path].get(term, 0)
                + normal_complex_noun_counts_main[file_path].get(term, 0)
                + two_word_complex_noun_counts_main[file_path].get(term, 0)
            )
            if count > 0:
                term_presence[term] += 1  # Increment presence count if term appears in the file
                term_frequencies[term] += count  # Accumulate total frequency

    filtered_terms = [
        term for term, presence in term_presence.items() if presence > threshold_main
    ]

    # Sort terms by presence count and total frequency (least frequent last)
    sorted_terms = sorted(
        filtered_terms, 
        key=lambda term: (term_presence[term], term_frequencies[term]),
        reverse=True,  # Reverse for descending order
    )

    # Create the Polars DataFrame
    term_data = {term: [] for term in sorted_terms}
    for file_path in word_counts_main.keys():
        for term in sorted_terms:
            count = (
                word_counts_main[file_path].get(term, 0)
                + normal_complex_noun_counts_main[file_path].get(term, 0)
                + two_word_complex_noun_counts_main[file_path].get(term, 0)
            )
            term_data[term].append(count)

    df = pl.DataFrame(term_data)
    df = df.transpose(include_header=True)
    df = df.rename({col: path for col, path in zip(df.columns[1:], word_counts_main.keys())})

    print("\nRanked Polars DataFrame with Filtered Terms:")
    print(df)

    return df


def main():
    if len(sys.argv) < 2:
        print("Usage: python script.py <main_folder_path> [<subtract_folder_path>]")
        sys.exit(1)

    main_folder = sys.argv[1]
    subtract_folder = sys.argv[2] if len(sys.argv) > 2 else None
    df = process_with_optional_subtract(main_folder, subtract_folder)

    # Save the DataFrame to a CSV (optional)
    output_path = os.path.join(main_folder, "filtered_common_terms.csv")
    df.write_csv(output_path)
    print(f"\nDataFrame saved to {output_path}")


if __name__ == "__main__":
    main()
