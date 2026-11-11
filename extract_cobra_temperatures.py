"""
Extract temperature arrays from a COBRA-EN output text file.

Usage:
    python extract_cobra_temperatures.py
        Opens a file picker.

    python extract_cobra_temperatures.py "C:\\path\\to\\cobra_output.txt"
        Reads the specified file.

The script extracts data for the first "TEMPERATURE DATA FOR ROD 1"
and first matching "HEAT TRANSFER DATA FOR ROD 1" section.
It prints the NumPy arrays and saves them in a .npz file beside the
input text file.
"""

from pathlib import Path
import re
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
            title="Select COBRA-EN output text file",
            filetypes=[
                ("Text/output files", "*.txt *.out *.dat"),
                ("All files", "*.*"),
            ],
        )
        root.destroy()
        return Path(filename) if filename else None
    except Exception as exc:
        raise RuntimeError(
            "Could not open the file picker. Run the script with the "
            "input filename as an argument."
        ) from exc


def numeric_rows(section_text, minimum_columns):
    """Read whitespace-separated numeric rows from a COBRA table."""
    rows = []
    for line in section_text.splitlines():
        fields = line.split()
        if len(fields) < minimum_columns:
            continue
        try:
            values = [float(value.replace("D", "E").replace("d", "e"))
                      for value in fields]
        except ValueError:
            continue
        rows.append(values)
    return rows


def find_section(text, section_title, next_marker):
    """Return the text between a section title and the next TIME section."""
    start = text.upper().find(section_title.upper())
    if start == -1:
        raise ValueError(f"Could not find section: {section_title}")

    end = text.upper().find(next_marker.upper(), start + len(section_title))
    if end == -1:
        end = len(text)

    return text[start:end]


def extract_arrays(input_path):
    text = input_path.read_text(encoding="utf-8", errors="replace")

    # Fuel/cladding temperatures:
    # columns: DISTANCE, FLUX, DNBR, CHANNEL, AV FUEL T,
    #          T(1), T(2), T(3), T(4), T(5), T(6), T(7)
    fuel_section = find_section(
        text,
        "TEMPERATURE DATA FOR ROD",
        "HEAT TRANSFER DATA FOR ROD",
    )
    fuel_rows = numeric_rows(fuel_section, minimum_columns=12)

    if not fuel_rows:
        raise ValueError("No numeric rows found in the fuel temperature table.")

    fuel_data = np.asarray(fuel_rows, dtype=float)

    # Heat-transfer table: DISTANCE, H.T.MODE, HSURF, HGAP, TFLUID
    heat_section = find_section(
        text,
        "HEAT TRANSFER DATA FOR ROD",
        "EPRI CRITICAL HEAT FLUX SUMMARY",
    )
    heat_rows = numeric_rows(heat_section, minimum_columns=5)

    if not heat_rows:
        raise ValueError("No numeric rows found in the heat-transfer table.")

    heat_data = np.asarray(heat_rows, dtype=float)

    # Match the coolant values to the fuel table by axial distance.
    fuel_z = fuel_data[:, 0]
    heat_z = heat_data[:, 0]

    if len(fuel_z) != len(heat_z) or not np.allclose(fuel_z, heat_z):
        raise ValueError(
            "The axial distances in the fuel and heat-transfer tables do "
            "not match. Check that both tables refer to the same rod."
        )

    arrays = {
        "z_coordinates": fuel_data[:, 0],
        "fuel_average": fuel_data[:, 4],
        "fuel_centreline": fuel_data[:, 5],       # T(1)
        "clad_inner_surface": fuel_data[:, 10],  # T(6)
        "clad_outer_surface": fuel_data[:, 11],  # T(7)
        "coolant_temperature": heat_data[:, 4],  # TFLUID
    }

    return arrays


def main():
    if len(sys.argv) > 1:
        input_path = Path(sys.argv[1]).expanduser()
    else:
        input_path = choose_input_file()

    if input_path is None:
        print("No file selected. Exiting.")
        return

    if not input_path.is_file():
        raise FileNotFoundError(f"File not found: {input_path}")

    arrays = extract_arrays(input_path)

    print(f"\nSuccessfully extracted data from:\n{input_path}\n")
    for name, values in arrays.items():
        print(f"{name} = np.array({np.array2string(values, separator=', ')})\n")

    output_path = input_path.with_name(input_path.stem + "_temperature_arrays.npz")
    np.savez(output_path, **arrays)

    print(f"Saved all six arrays to:\n{output_path}")
    print("\nTo load them in another Python script, use:")
    print(f' data = np.load(r"{output_path}")')
    print(' z_coordinates = data["z_coordinates"]')
    print(' fuel_average = data["fuel_average"]')
    print(' fuel_centreline = data["fuel_centreline"]')
    print(' clad_inner_surface = data["clad_inner_surface"]')
    print(' clad_outer_surface = data["clad_outer_surface"]')
    print(' coolant_temperature = data["coolant_temperature"]')


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"\nERROR: {error}")
        input("\nPress Enter to close...")
