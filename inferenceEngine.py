import pandas as pd
import numpy as np
import resto as resto
import requests
import json
from datetime import datetime
from pathlib import Path
from functools import lru_cache

# Current file's directory (app.py's location)
app_dir = Path(__file__).parent

muutujad_path = app_dir / "teadmusbaas" / "muutujad.xlsx"
kb_path = app_dir / "teadmusbaas" / "teadmusbaas.xlsx"
korterelamud_path = app_dir / "teadmusbaas" / "eesti-korterelamud.xlsx"
typo_path = app_dir / "teadmusbaas" / "tüpoloogia.xlsx"

df_vs = pd.read_excel(kb_path, sheet_name='vs')
df_ohuleke = pd.read_excel(kb_path, sheet_name='õhuleke')
df_korterelamud = pd.read_excel(korterelamud_path, sheet_name='Ilma>1995')
df_typoloogia = pd.read_excel(typo_path, sheet_name="Tüpoloogia tabel")

ehr_url = "https://livekluster.ehr.ee/api/building/v2/buildingData"
digikaksik_url = "https://livekluster.ehr.ee/api/3dtwin/v1/rest-api/particles?bbox=542914.54,6589115.305,542915.54,6589116.305"
maaamet_url = "https://gpa.maaamet.ee/api/"  # Maa-ameti Geodeesia teenused

YMBRUSE_R = 100


@lru_cache(maxsize=128)  # Adjust maxsize according to your needs
def get_ehr_data(ehr_kood):
    start_time = datetime.now()  # Start timing for feedback
    response = requests.get(ehr_url + '?ehr_code=' + str(ehr_kood))
    print("get_ehr runtime: ", datetime.now() - start_time)
    return json.loads(response.text)


# Function to cache and read an Excel file, returning a pandas DataFrame of the entire file
@lru_cache(maxsize=None)
def read_excel_file_cached(file_path):
    return pd.ExcelFile(file_path)


# Function to read a specific sheet from the cached Excel file
def read_excel_sheet(file_path, sheet_name):
    excel_file = read_excel_file_cached(file_path)
    return excel_file.parse(sheet_name)


def get_muutujad_excel_sheet(sheet_name):
    return read_excel_sheet(muutujad_path, sheet_name)


def get_kb_excel_sheet(sheet_name):
    return read_excel_sheet(kb_path, sheet_name)


def get_korterelamud_excel_sheet(sheet_name):
    return read_excel_sheet(korterelamud_path, sheet_name)


def get_typo_excel_sheet(sheet_name):
    return read_excel_sheet(typo_path, sheet_name)


# Function to extract a column as a list from a given DataFrame
def get_column_list_from_df(df, column_name):
    return df[column_name].tolist()


def get_vs_u(params, **kwargs):
    return df_vs.loc[df_vs['nimetus'] == params.etapp_2.vs, 'U-arv'].iloc[0]


def get_vs_paksus(params, **kwargs):
    return str(df_vs.loc[df_vs['nimetus'] == params.etapp_2.vs, 'Paksus'].iloc[0])


def get_ohuleke_vaartus(params, **kwargs):
    return str(df_ohuleke.loc[df_ohuleke['nimetus'] == params.etapp_2.ohuleke, 'väärtus'].iloc[0])


def get_typo_kood(ehr_kood):
    try:
        t = df_korterelamud.loc[df_korterelamud['EHR kood'] == ehr_kood, 'T_kood'].iloc[0]
    except:
        t = 'Pole teada'
    return t


def app_get_typo_kood(params, **kwargs):
    return get_typo_kood(params.etapp_1.ehr)


def get_typo_df(typo_kood):
    """Tüpooloogia Excelist kõikide tüpoloogiat iseloomustavate statistiliste parameetrite toomine."""
    if typo_kood == 'Pole teada' or typo_kood is None:
        return None
    df = (df_typoloogia.loc[:, ['Kategooria', 'Nimetus', 'Ühik', 'Tähis', typo_kood]]
          .ffill()
          .set_index('Tähis')
          .rename(columns={typo_kood: 'väärtus'}))
    return df


def get_building_ehr_info(ehr_kood):
    """Toome kõik EhR-i avaandmed ühte DataFrame'i"""
    start_time = datetime.now()  # Start timing for feedback

    ehr_json = get_ehr_data(ehr_kood)

    ruumikuju = ehr_json['ehitis']['ehitiseKujud']['ruumikuju'][0]
    geometry = ruumikuju['geometry']
    viitepunkt_x = float(ruumikuju['viitepunktX'])
    viitepunkt_y = float(ruumikuju['viitepunktY'])
    maakond = ruumikuju['ehitiseKujuAadressid']['aadress'][0]['tase1_nimetus']
    kov = ruumikuju['ehitiseKujuAadressid']['aadress'][0]['tase2_nimetus']
    taisaadress = ehr_json['ehitis']['ehitiseAndmed']['taisaadress']
    esmanekasutus = ehr_json['ehitis']['ehitiseAndmed']['esmaneKasutus']
    kasutusotstarve_kood = int(ehr_json['ehitis']['ehitiseKasutusotstarbed']['kasutusotstarve'][0]['kaosKood'])
    kasutusotstarve_tekst = ehr_json['ehitis']['ehitiseKasutusotstarbed']['kasutusotstarve'][0]['kaosIdTxt']

    # Ehitise tehniliste näitajate default väärtused
    valisseina_liik = "Pole teada"
    kandekonstr_mat = "Pole teada"
    valissein_viimistlus = "Pole teada"
    soojusvarustuse_liik = "Pole teada"
    soojusallika_liik = "Pole teada"
    energiaallika_liik = "Pole teada"
    ventilatsiooni_liik = "Pole teada"
    jahutuse_liik = "Pole teada"
    gaas = "Pole teada"

    for tehn_naitaja in ehr_json['ehitis']['ehitiseTehnilisedNaitajad']['tehnilineNaitaja']:
        if tehn_naitaja['klNimetus'] == 'Välisseina liik':
            valisseina_liik = tehn_naitaja['nimetus']
        elif tehn_naitaja['klNimetus'] == 'Kande- ja jäigastavate konstruktsioonide materjal':
            kandekonstr_mat = tehn_naitaja['nimetus']
        elif tehn_naitaja['klNimetus'] == 'Välisseina välisviimistluse materjal':
            valissein_viimistlus = tehn_naitaja['nimetus']
        elif tehn_naitaja['klNimetus'] == 'Soojusvarustuse liik':
            soojusvarustuse_liik = tehn_naitaja['nimetus']
        elif tehn_naitaja['klNimetus'] == 'Soojusallikas':
            soojusallika_liik = tehn_naitaja['nimetus']
        elif tehn_naitaja['klNimetus'] == 'Energiaallikas':
            energiaallika_liik = tehn_naitaja['nimetus']
        elif tehn_naitaja['klNimetus'] == 'Ventilatsiooni liik':
            ventilatsiooni_liik = tehn_naitaja['nimetus']
        elif tehn_naitaja['klNimetus'] == 'Jahutussüsteemi liik':
            jahutuse_liik = tehn_naitaja['nimetus']
        elif tehn_naitaja['klNimetus'] == 'Võrgu- või mahutigaasi olemasolu':
            gaas = tehn_naitaja['nimetus']

    all_coords = geometry['coordinates'][0]
    min_x = min(coord[0] for coord in all_coords) + 1
    max_x = max(coord[0] for coord in all_coords) - 1
    min_y = min(coord[1] for coord in all_coords) + 1
    max_y = max(coord[1] for coord in all_coords) - 1
    avg_x = (min_x + max_x) / 2
    avg_y = (min_y + max_y) / 2
    bbox = "{},{},{},{}".format(avg_x, avg_y, avg_x + 1, avg_y + 1)
    bbox_ymbrus = "{},{},{},{}".format(avg_x - YMBRUSE_R, avg_y - YMBRUSE_R, avg_x + YMBRUSE_R, avg_y + YMBRUSE_R)

    max_korruste_arv = int(ehr_json['ehitis']['ehitisePohiandmed']['maxKorrusteArv'])
    ehitisalune_pind = float(ehr_json['ehitis']['ehitisePohiandmed']['ehitisalunePind'])
    netopind = float(ehr_json['ehitis']['ehitisePohiandmed']['suletud_netopind'])
    maaaluste_korruste_arv = abs(int(ehr_json['ehitis']['ehitisePohiandmed'].get('maaalusteKorrusteArv', 0)))

    energiamargised = ehr_json['ehitis']['ehitiseEnergiamargised']['energiamargis']
    if energiamargised:
        energiamargis = ehr_json['ehitis']['ehitiseEnergiamargised']['energiamargis'][0]
        etakek_tyyp = energiamargis['etaKekType']
        try:
            etakek_value = float(energiamargis['etaKekVal'])
        except:
            etakek_value = None
        energaklass = energiamargis['energiaKlass']
        try:
            koetav_pind = float(energiamargised[0].get('koetavPind', netopind))
        except:
            koetav_pind = None
    else:
        etakek_tyyp = None
        etakek_value = None
        energaklass = None
        koetav_pind = netopind

    '''RESTO sisendid:
                ['E1', 'E3', 'E6', 'E7', 'E10', 'E11', 'E12', 'E19',
                'E21', 'E25', 'E26', 'E27', 'E28', 'E29', 'E30', 'E31', 'E32', 'E33',
                'L6', 'L9', 'L11', 'L12', 'L13', 'L14', 'L15', 'L16', 'L17', 'L18', <- pindalad leiame hiljem
                'L21', 'L22', 'L24', 'L26', 'L27', <- joonkülmasillad leiame hiljem
                'T8', 'T11', <- uste pindala ja kinnituste pikkus kokku
                'T12', 'T13', 'T15', 'T17', 'T18', 'T19', 'T20', 'T22', 'T24', 'T25', 'T26', 'T27', <- soojusläbivused
                'T41', 'R312', 'R313', 'R314', 'R315', 'R316', 'R317', 'R318', 'R319', <- akende ja fas pindalade suhe
                'C1', 'C2', 'C66', 'C67', 'C34', 'C35', 'C41', 'C42', 'R63'] <- resto.get_defaults()'''
    ehitise_andmed = pd.Series({'E1': ehr_kood,
                                'bbox': bbox,
                                'bbox_ymbrus': bbox_ymbrus,
                                'viitepunktXY': [viitepunkt_x, viitepunkt_y],
                                'energiamargis': {'tyyp': etakek_tyyp, 'arv': etakek_value, 'klass': energaklass},
                                'E3': taisaadress,
                                'E4': maakond,
                                'E5': kov,
                                'E6': kasutusotstarve_kood,
                                'E7': kasutusotstarve_tekst,
                                'E9': ehitisalune_pind,
                                'E10': max_korruste_arv,
                                'E11': maaaluste_korruste_arv,
                                'E12': esmanekasutus,
                                'E19': netopind,
                                'E21': koetav_pind,
                                'E25': valisseina_liik,
                                'E26': kandekonstr_mat,
                                'E27': valissein_viimistlus,
                                'E28': soojusvarustuse_liik,
                                'E29': soojusallika_liik,
                                'E30': energiaallika_liik,
                                'E31': ventilatsiooni_liik,
                                'E32': jahutuse_liik,
                                'E33': gaas,
                                }, name='väärtus')

    # print("get_building_ehr_info() runtime: ", datetime.now() - start_time)
    # return Pandas.Series type
    return ehitise_andmed


def get_building_geometry_values():
    # TODO: Arvuta erinevatesse ilmakaartesse vaatavad seinad.
    """''L6', 'L9', 'L11', 'L12', 'L13', 'L14', 'L15', 'L16', 'L17', 'L18', <- pindalad leiame hiljem
    L21', 'L22', 'L24', 'L26', 'L27', <- joonkülmasillad leiame hiljem
    'T8', 'T11', <- uste pindala ja kinnituste pikkus kokku
    'T12', 'T13', 'T15', 'T17', 'T18', 'T19', 'T20', 'T22', 'T24', 'T25', 'T26', 'T27', <- soojusläbivused
    'T41', 'R312', 'R313', 'R314', 'R315', 'R316', 'R317', 'R318', 'R319', <- akende ja fas pindalade suhe"""

    # Placeholder väärtused võetud RESTO Tartu tester Excelist, hoone 104018667
    ps = pd.Series({
        "L11": 233.6,
        "L12": 0,
        "L13": 1299.1,
        "L14": 0,
        "L15": 233.6,
        "L16": 0,
        "L17": 1269.1,
        "L18": 0,
        "L6": 539.6,
        "L8": 0,
        "L9": 539.64,
        "L10": 0,
        "L21": 392.32,
        "L22": 184.22,
        "L23": 0,
        "L24": 141.04,
        "L25": 0,
        "L26": 987.28,
        "L27": 608.4,
        # "T8": 7.9,
        "T11": 1862.42,
        "R312": 0.0,
        "R313": 0.0,
        "R314": 0.2,
        "R315": 0.0,
        "R316": 0.0,
        "R317": 0.0,
        "R318": 0.3,
        "R319": 0.0,
        # "T12": 0.8, Väärtused tulevad otse tüpoloogiast
        # "T13": 0.9,
        # "T14": 0.0,
        # "T15": 0.15,
        # "T16": 0.7,
        # "T17": 2.0,
        # "T18": 2.4,
        # "T19": 1.17,
        # "T20": 0.49,
        # "T21": 0.0,
        # "T22": 0.15,
        # "T23": 0.5,
        # "T24": 0.77,
        # "T25": 1.03,
        # "T26": 0.07,
        # "T27": 6.0,
        # "T41": 0.25,
    }, name='väärtus')
    return ps


def get_building_df(ehr_kood):
    """Paneme kõikide erinevate allikate andmed ühte DataFrame-i"""
    start_time = datetime.now()  # Start timing for feedback

    ehr_andmed = get_building_ehr_info(ehr_kood)

    # Hoone tüpoloogia tunnuskood, alati str
    typo_kood = get_typo_kood(ehr_kood)

    # Tunnuskoodile vastavad statistilised andmed DataFrame-ina, võib olla None kui tüüp pole teada
    typo_df = get_typo_df(typo_kood)

    if typo_df is None:
        typo_andmed = None
        andmed2 = pd.Series({
            'T1': typo_kood,
        }, name='väärtus')
    else:
        typo_andmed = typo_df.rename(columns={typo_kood: 'väärtus'})

        trepikodade_arv = resto.get_trepikodade_arv(ehr_andmed)
        andmed2 = pd.Series({
            'T1': typo_kood,
            'E8': int(trepikodade_arv),
            'T8': float(trepikodade_arv * typo_andmed['väärtus']['T54'] * typo_andmed['väärtus']['T55']),
        }, name='väärtus')

    pindalad = get_building_geometry_values()

    defaults = resto.get_defaults()

    data = pd.concat([ehr_andmed, andmed2, typo_andmed, defaults, pindalad])

    # Print runtime of the calculation
    # print("get_building_df() runtime: ", datetime.now() - start_time)
    return data


def convert_coordinates(x, y, dirGeoToLest=True):
    """
    Convert coordinates between global coordinates and Estonian L-EST.

    Parameters:
    - x: The X coordinate (latitude for global, L-EST X for Estonian L-EST).
    - y: The Y coordinate (longitude for global, L-EST Y for Estonian L-EST).
    - dirGeoToLest: Direction of conversion. True for Geo to L-EST, False for L-EST to Geo.

    Returns:
    A dictionary with the converted coordinates and name (if available).
    """
    # Define the URL with parameters for conversion
    url = f"{maaamet_url}geolest?x={x}&y={y}&dirGeoToLest={'true' if dirGeoToLest else 'false'}"

    try:
        # Make the GET request to the conversion service
        response = requests.get(url)
        response.raise_for_status()  # Raises an exception for 4XX/5XX errors

        # Parse the JSON response
        converted_data = response.json()

        # Return the converted coordinates
        return converted_data

    except requests.RequestException as e:
        print(f"Error during conversion: {e}")
        return None


def convert_coordinates_mass(inputData, dirGeoToLest=True):
    """
    Convert a batch of coordinates between global coordinates and Estonian L-EST.

    Parameters:
    - inputData: A list of dictionaries, each containing "nimi", "x", and "y" keys.
    - dirGeoToLest: Direction of conversion. True for Geo to L-EST, False for L-EST to Geo.

    Returns:
    A JSON response from the API with converted coordinates.
    """
    url = f"{maaamet_url}geolest"

    headers = {'Content-Type': 'application/json'}
    payload = {
        "dirGeoToLest": dirGeoToLest,
        "inputData": inputData
    }

    try:
        # Make the POST request to the conversion service with the mass query
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        response.raise_for_status()  # Raises an exception for 4XX/5XX errors

        # Parse and return the JSON response
        return response.json()

    except requests.RequestException as e:
        print(f"Error during mass conversion: {e}")
        return None


def get_katastri_koordinaadid(bbox_lest):
    start_time = datetime.now()  # Start timing for feedback
    # URL to fetch data in GeoJSON format from the "kataster:ky_kehtiv" collection
    url = "https://gsavalik.envir.ee/geoserver/ogc/features/collections/kataster:ky_kehtiv/items?f=application%2Fgeo%2Bjson"

    # Optional: Specify query parameters, such as a bounding box, limit, etc.
    # Example: parameters to fetch the first 100 features (modify as needed)
    params = {
        'bbox': bbox_lest,  # '24.7,59.4,24.71,59.41', specify a bounding box (minLon,minLat,maxLon,maxLat)
        'limit': 10  # Example: limit to retrieve the first 100 features
    }

    response = requests.get(url, params=params)

    polygons = []

    if response.status_code == 200:
        collections = response.json()
        # print(collections['features'][0])
        for feature in collections['features']:
            for polygon in feature['geometry']['coordinates']:
                latlon = [{"x": lat, "y": lon} for lon, lat in polygon]
                l_est = convert_coordinates_mass(latlon)
                coordinates = [[entry["y"], entry["x"]] for entry in l_est]
                polygons.append(coordinates)
    else:
        print("Failed to fetch data, status code:", response.status_code)
        return None

    # Print runtime of the calculation
    print("get_katastri_koordinaadid() runtime: ", datetime.now() - start_time)
    return polygons


def infer_vana(ehr_kood):
    """Loome algandmetest uusi teadmisi hoone kohta."""
    start_time = datetime.now()  # Start timing for feedback

    data = get_building_df(ehr_kood)
    muutujad = resto.get_muutujad()

    if data is None:
        return "No data!"

    if data['väärtus']['T1'] != 'Pole teada':
        r1tor18data = resto.calculate_R1_to_R18(data['väärtus'])
        envelope_H = None  # resto.calculate_envelope_H(data['väärtus'])
        data = pd.concat([data, r1tor18data, envelope_H])
    else:
        print("Hoone tüübi kategooria pole teada, seega RESTO funktsioonid ei käivitu!")

    print("infer() runtime: ", datetime.now() - start_time)  # Print runtime of the calculation
    return data


def set_nimetus_column(data):
    muutujad = get_muutujad_excel_sheet('Muutujate andmebaas')
    code_to_name_map = muutujad.set_index('Uus kood')['Nimetus'].to_dict()

    # Update 'Nimetus' column with mapping, default to index if no match is found
    data['Nimetus'] = data.index.map(lambda x: code_to_name_map.get(x, x))
    return data


def infer(ehr_kood):
    """Loome algandmetest uusi teadmisi hoone kohta."""
    start_time = datetime.now()  # Start timing for feedback

    data = get_building_df(ehr_kood)
    muutujad = get_muutujad_excel_sheet('Muutujate andmebaas')

    if data is None or muutujad is None:
        return "No data!"

    if data.loc['T1', 'väärtus'] != 'Pole teada':  # Adjusted for potential indexing method
        r1tor18data = resto.calculate_R1_to_R18(data['väärtus'])
        envelope_H = None  # resto.calculate_envelope_H(data['väärtus'])
        data = pd.concat([data, r1tor18data, envelope_H], axis=0, sort=False)
    else:
        print("Hoone tüübi kategooria pole teada, seega RESTO funktsioonid ei käivitu!")

    # Nimetuse col määramine 'muutujad.xlsx' faili järgi
    data = set_nimetus_column(data)

    print("infer() runtime: ", datetime.now() - start_time)  # Print runtime of the calculation
    return data

# print(get_katastri_koordinaadid(data['väärtus']['bbox_ymbrus']))


def export_infer_json(ehr_kood):
    building_df = infer(ehr_kood)
    # print("Duplicates in DataFrame: " + str(any(building_df.index.duplicated())))
    building_df = building_df[~building_df.index.duplicated(keep='first')]
    building_series = building_df['väärtus']
    building_series = building_series.apply(lambda x: x.item() if isinstance(x, np.generic) else x)

    json_file_path = 'G:/Downloads/eksport_naide.json'
    building_series.to_json(json_file_path, orient='index', force_ascii=False)  # This ensures UTF-8 encoding

    print(f'Data exported successfully to {json_file_path}')


#print(infer(101020350))
# export_infer_json(101020350)
