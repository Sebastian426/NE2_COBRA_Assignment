
"""
Extract temperature and void fraction arrays from a COBRA-EN
BWR output text file.

Usage:
    python extract_bwr_temperatures.py

    Opens a file picker.

    python extract_bwr_temperatures.py "C:\\path\\to\\cobra_output.txt"

    Reads the specified file.

The script extracts data from the first:
    - TEMPERATURE DATA FOR ROD 1
    - HEAT TRANSFER DATA FOR ROD 1
    - RESULTS FOR CHANNEL 1

The extracted arrays are printed and saved in a .npz file
beside the input text file.
"""

from pathlib import Path
import sys

import numpy as np


def choose_input_file():
    """Show a Windows file picker if no filename was supplied."""

    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)

        filename = filedialog.askopenfilename(
            title="Select COBRA-EN BWR output text file",
            filetypes=[
                ("Text/output files", "*.txt *.out *.dat"),
                ("All files", "*.*"),
            ],
        )

        root.destroy()

        return Path(filename) if filename else None

    except Exception as exc:
        raise RuntimeError(
            "Could not open the file picker. Run the script with "
            "the input filename as an argument."
        ) from exc


def numeric_rows(section_text, minimum_columns):
    """Read whitespace-separated numeric rows from a COBRA table."""

    rows = []

    for line in section_text.splitlines():

        fields = line.split()

        if len(fields) < minimum_columns:
            continue

        try:
            values = [
                float(value.replace("D", "E").replace("d", "e"))
                for value in fields
            ]

        except ValueError:
            continue

        rows.append(values)

    return rows


def find_section(text, section_title, next_markers):
    """
    Return the text between a section title and the next section.

    Uses the first occurrence of the requested section title.
    """

    text_upper = text.upper()

    start = text_upper.find(section_title.upper())

    if start == -1:
        raise ValueError(
            f"Could not find section: {section_title}"
        )

    search_start = start + len(section_title)

    # Find the earliest subsequent section marker
    end_positions = []

    for marker in next_markers:

        position = text_upper.find(
            marker.upper(),
            search_start
        )

        if position != -1:
            end_positions.append(position)

    end = min(end_positions) if end_positions else len(text)

    return text[start:end]


def extract_arrays(input_path):

    text = input_path.read_text(
        encoding="utf-8",
        errors="replace"
    )

    # ##################################################
    # Fuel and cladding temperatures
    # ##################################################

    # Columns:
    # 0: DISTANCE
    # 1: FLUX
    # 2: DNBR
    # 3: CHANNEL
    # 4: AV FUEL T
    # 5: T(1) - Fuel centreline
    # 6: T(2)
    # 7: T(3)
    # 8: T(4)
    # 9: T(5)
    # 10: T(6) - Clad inner surface
    # 11: T(7) - Clad outer surface

    fuel_section = find_section(
        text,
        "TEMPERATURE DATA FOR ROD",
        ["HEAT TRANSFER DATA FOR ROD"]
    )

    fuel_rows = numeric_rows(
        fuel_section,
        minimum_columns=12
    )

    if not fuel_rows:
        raise ValueError(
            "No numeric rows found in the fuel temperature table."
        )

    fuel_data = np.asarray(fuel_rows, dtype=float)


    # ##################################################
    # Heat-transfer data
    # ##################################################

    # Columns:
    # 0: DISTANCE
    # 1: H.T.MODE
    # 2: HSURF
    # 3: HGAP
    # 4: TFLUID

    heat_section = find_section(
        text,
        "HEAT TRANSFER DATA FOR ROD",
        [
            "RESULTS FOR CHANNEL",
            "PROBLEM TITLE"
        ]
    )

    heat_rows = numeric_rows(
        heat_section,
        minimum_columns=5
    )

    if not heat_rows:
        raise ValueError(
            "No numeric rows found in the heat-transfer table."
        )

    heat_data = np.asarray(heat_rows, dtype=float)


    # ##################################################
    # Void fraction distribution
    # ##################################################

    # Columns:
    # 0: DISTANCE
    # 1: DELTA-P
    # 2: ENTHALPY
    # 3: TEMPERATURE
    # 4: DENSITY
    # 5: FLOWING QUALITY
    # 6: VOID FRACTION
    # 7: FLOW
    # 8: MASS FLUX
    # 9: BORON
    # 10: CHF
    # 11: CHF TEMP

    void_section = find_section(
        text,
        "RESULTS FOR CHANNEL",
        [
            "RESULTS FOR CHANNEL",
            "PROBLEM TITLE",
            "TIME ="
        ]
    )

    void_rows = numeric_rows(
        void_section,
        minimum_columns=12
    )

    if not void_rows:
        raise ValueError(
            "No numeric rows found in the void fraction table."
        )

    void_data = np.asarray(void_rows, dtype=float)


    # ##################################################
    # Check axial coordinates
    # ##################################################

    fuel_z = fuel_data[:, 0]
    heat_z = heat_data[:, 0]
    void_z = void_data[:, 0]

    # Temperature and heat-transfer coordinates should match

    if (
        len(fuel_z) != len(heat_z)
        or not np.allclose(fuel_z, heat_z)
    ):
        raise ValueError(
            "The axial distances in the fuel and heat-transfer "
            "tables do not match."
        )


    # ##################################################
    # Extract final arrays
    # ##################################################

    arrays = {

        # Axial coordinates
        "z_temperature": fuel_z,
        "z_void_fraction": void_z,

        # Fuel and cladding temperatures
        "fuel_average": fuel_data[:, 4],
        "fuel_centreline": fuel_data[:, 5],
        "clad_inner_surface": fuel_data[:, 10],
        "clad_outer_surface": fuel_data[:, 11],

        # Coolant temperature
        "coolant_temperature": heat_data[:, 4],

        # Void fraction
        "void_fraction": void_data[:, 6],

    }

    return arrays


def main():

    # Select input file

    if len(sys.argv) > 1:
        input_path = Path(sys.argv[1]).expanduser()

    else:
        input_path = choose_input_file()

    if input_path is None:
        print("No file selected. Exiting.")
        return

    if not input_path.is_file():
        raise FileNotFoundError(
            f"File not found: {input_path}"
        )


    # Extract arrays

    arrays = extract_arrays(input_path)


    # ##################################################
    # Print extracted arrays
    # ##################################################

    print(
        f"\nSuccessfully extracted data from:\n{input_path}\n"
    )

    for name, values in arrays.items():

        print(
            f"{name} = np.array("
            f"{np.array2string(values, separator=', ')})\n"
        )


    # ##################################################
    # Save arrays to NPZ file
    # ##################################################

    output_path = input_path.with_name(
        input_path.stem + "_BWR_arrays.npz"
    )

    np.savez(
        output_path,
        **arrays
    )

    print(
        f"Saved all eight arrays to:\n{output_path}"
    )


    # ##################################################
    # Instructions for loading arrays
    # ##################################################

    print("\nTo load them in another Python script, use:")

    print(f'\ndata = np.load(r"{output_path}")')

    for name in arrays:
        print(f'{name} = data["{name}"]')


if __name__ == "__main__":

    try:
        main()

    except Exception as error:

        print(f"\nERROR: {error}")

        input("\nPress Enter to close...")
