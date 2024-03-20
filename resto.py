from datetime import datetime
import pandas as pd
import numpy as np


def get_muutujad():
    # Reading data from Excel
    excel_path = "teadmusbaas/muutujad.xlsx"
    data = pd.read_excel(excel_path, sheet_name="Muutujate andmebaas", na_values=["NA", "#DIV/0!", "", "?"])
    return data


def get_muutuja_tahendus(muutuja_kood):
    muutujad = get_muutujad()
    return muutujad[muutujad['Uus kood'] == muutuja_kood]['Nimetus'].to_string(index=False)


def get_trepikodade_arv(data):
    """Empiiriline valem hoone ligikautse trepikodade arvu leidmiseks.
    Kredexi 400se valimiga võrreldes on selle valemi R-ruut vaid 0.67, seega pole tegemist kuigi täpse väärtusega."""
    netopindala = data['E19']
    korruste_arv = data['E10']
    return round(netopindala / korruste_arv / 150)


def get_defaults():
    """RESTO sisendite 'C1', 'C2', 'C66', 'C67', 'C34', 'C35', 'C41', 'C42', 'R63' vaikeväärtuste määramine"""
    defaults = {
        'C1': 21.0,  # Indoor temperature
        'C2': 1.25,  # Average outdoor temperature during heating period
        'C66': 0.8,  # Window glazing area as a fraction of total window area
        'C67': 0.6,  # Solar factor of window glazing
        'C34': 0.75,  # Specific Fan Power (SFP) for supply side of ventilation system
        'C35': 0.75,  # SFP for exhaust side of ventilation system
        'C41': 0.8,  # Efficiency of heat recovery in ventilation system
        'C42': 18.0,  # Assumed temperature of ventilation air after heat exchanger
        'R63': 1.0  # Efficiency of hot water distribution system in calc - currently 1 according to ETMN
    }

    # Create a DataFrame from the defaults dictionary
    # The keys become the index, and the values are under the 'väärtus' column
    defaults_df = pd.DataFrame.from_dict(defaults, orient='index', columns=['väärtus'])

    return defaults_df


def vana_calculate_R1_to_R18(data):
    """Otse RESTOst, aint et sisendiks on Series, mitte Dataframe (st üks andmerida)
    Siit tulevad arvutuspindalad ja mõned muud olulisemad arvutusparameetrid"""

    # Check if R312 exists, indicating use of specific data for window areas
    if "R312" in data:
        for r, l, ratio in zip(["R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8"],
                               ["L11", "L12", "L13", "L14", "L15", "L16", "L17", "L18"],
                               ["R312", "R313", "R314", "R315", "R316", "R317", "R318", "R319"]):
            data[r] = data[l] * data[ratio]
    else:
        # Default calculation using T41 for window areas
        for r, l in zip(["R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8"],
                        ["L11", "L12", "L13", "L14", "L15", "L16", "L17", "L18"]):
            data[r] = data[l] * data['T41']

    # Calculate external wall area excluding windows and doors (R9)
    data['R9'] = sum([data.get(key, 0) for key in ["L11", "L12", "L13", "L14", "L15", "L16", "L17", "L18"]]) - \
                 sum([data.get(key, 0) for key in ["T8", "R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8"]])

    # Other areas calculations
    data['R10'] = data['L6']  # Ceiling
    data['R12'] = data['L9']  # Floor on ground
    # Total enclosure area (R15)
    data['R15'] = sum(
        data.get(key, 0) for key in ["L11", "L12", "L13", "L14", "L15", "L16", "L17", "L18", "R10", "R12"])

    # Number of floors (R16)
    data['R16'] = data['E10'] + data['E11']

    # Air leakage rate (R17) calculation based on the number of floors
    conditions = [
        data['R16'] < 2,
        data['R16'] < 3,
        data['R16'] < 5
    ]
    choices = [
        data['T27'] * data['R15'] / (3600 * 35),
        data['T27'] * data['R15'] / (3600 * 24),
        data['T27'] * data['R15'] / (3600 * 20)
    ]
    default = data['T27'] * data['R15'] / (3600 * 15)
    data['R17'] = np.select(conditions, choices, default=default)

    # Usage category according to regulations (R18)
    conditions = [
        (data['E6'] < 11200) & (data['E21'] <= 120),
        (data['E6'] < 11200) & (data['E21'] <= 220),
        (data['E6'] < 11200),
        (data['E6'] < 11300)
    ]
    choices = [1, 2, 3, 4]
    data['R18'] = np.select(conditions, choices, default=6)

    return data


def calculate_R1_to_R18(data):
    """Otse RESTOst, aint et sisendiks on Series, mitte Dataframe (st üks andmerida)
    Siit tulevad arvutuspindalad ja mõned muud olulisemad arvutusparameetrid"""
    new_values = {}

    # Check if R312 exists, indicating use of specific data for window areas
    if "R312" in data:
        for r, l, ratio in zip(["R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8"],
                               ["L11", "L12", "L13", "L14", "L15", "L16", "L17", "L18"],
                               ["R312", "R313", "R314", "R315", "R316", "R317", "R318", "R319"]):
            new_values[r] = data.get(l, 0) * data.get(ratio, 0)
    else:
        # Default calculation using T41 for window areas
        for r, l in zip(["R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8"],
                        ["L11", "L12", "L13", "L14", "L15", "L16", "L17", "L18"]):
            new_values[r] = data.get(l, 0) * data.get('T41', 0)

    # Calculate external wall area excluding windows and doors (R9)
    new_values['R9'] = sum([data.get(key, 0) for key in ["L11", "L12", "L13", "L14", "L15", "L16", "L17", "L18"]]) - \
                       sum([data.get(key, 0) for key in ["T8", "R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8"]])

    # Other areas calculations
    new_values['R10'] = data.get('L6', 0)  # Ceiling
    new_values['R12'] = data.get('L9', 0)  # Floor on ground
    # Total enclosure area (R15)
    new_values['R15'] = sum(
        data.get(key, 0) for key in ["L11", "L12", "L13", "L14", "L15", "L16", "L17", "L18", "R10", "R12"])

    # Number of floors (R16)
    new_values['R16'] = data.get('E10', 0) + data.get('E11', 0)

    # Air leakage rate (R17) calculation based on the number of floors
    conditions = [
        new_values['R16'] < 2,
        new_values['R16'] < 3,
        new_values['R16'] < 5
    ]
    choices = [
        data.get('T27', 0) * new_values['R15'] / (3600 * 35),
        data.get('T27', 0) * new_values['R15'] / (3600 * 24),
        data.get('T27', 0) * new_values['R15'] / (3600 * 20)
    ]
    default = data.get('T27', 0) * new_values['R15'] / (3600 * 15)
    new_values['R17'] = np.select(conditions, choices, default=default)

    # Usage category according to regulations (R18)
    conditions = [
        (data.get('E6', 0) < 11200) & (data.get('E21', 0) <= 120),
        (data.get('E6', 0) < 11200) & (data.get('E21', 0) <= 220),
        (data.get('E6', 0) < 11200),
        (data.get('E6', 0) < 11300)
    ]
    choices = [1, 2, 3, 4]
    new_values['R18'] = np.select(conditions, choices, default=6)

    # Create a new Series from the calculated values with 'väärtus' as the name
    return pd.Series(new_values, name='väärtus')


def calculate_envelope_H(ds):
    start_time = datetime.now()  # Start timing for feedback

    trepikodade_arv = int(ds['T8'])
    valisusteU = float(ds['T17'])

    # Calculate thermal losses for various building components
    ukseH = trepikodade_arv * valisusteU
    aknaH = (float(ds.get('R1', 0)) + float(ds.get('R2', 0)) + float(ds.get('R3', 0)) +
             float(ds.get('R4', 0)) + float(ds.get('R5', 0)) + float(ds.get('R6', 0)) +
             float(ds.get('R7', 0)) + float(ds.get('R8', 0))) * float(ds.get('T18', 0))
    seinaH = float(ds.get('R9', 0)) * float(ds.get('T12', 0))
    katuseH = float(ds.get('R10', 0)) * float(ds.get('T13', 0))
    porandaH = float(ds.get('R12', 0)) * float(ds.get('T15', 0))
    kylmasildadeH = (float(ds.get('L21', 0)) * float(ds.get('T19', 0)) + float(ds.get('L22', 0)) * float(
        ds.get('T20', 0)) +
                     float(ds.get('L24', 0)) * float(ds.get('T22', 0)) + float(ds.get('L26', 0)) * float(
                ds.get('T24', 0)) +
                     float(ds.get('L27', 0)) * float(ds.get('T25', 0)) + float(ds.get('T11', 0)) * float(
                ds.get('T26', 0)))
    ohulekkeH = float(ds.get('R17', 0)) * 1005 * 1.2
    kokkuvalispiireteH = ukseH + aknaH + seinaH + katuseH + porandaH + kylmasildadeH + ohulekkeH

    # Assign intermediate variables for output (for debugging or analysis)
    h_series = pd.Series({
        'R19': ukseH + aknaH,
        'R20': seinaH,
        'R21': katuseH,
        'R22': porandaH,
        'R23': kylmasildadeH,
        'R24': ohulekkeH,
        'R25': kokkuvalispiireteH
    }, name='väärtus')

    # Print runtime of the calculation
    # print("calculate_envelope_H runtime: ", datetime.now() - start_time)

    return h_series

print(get_muutujad())
